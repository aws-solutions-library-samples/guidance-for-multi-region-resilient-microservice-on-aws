package repository

import (
	"catalog/config"
	"catalog/model"
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"strings"
	"sync"
	"time"

	awsconfig "github.com/aws/aws-sdk-go-v2/config"
	"github.com/aws/aws-sdk-go-v2/service/secretsmanager"
	"github.com/dlmiddlecote/sqlstats"
	"github.com/go-sql-driver/mysql"
	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/mysql"
	_ "github.com/golang-migrate/migrate/v4/source/file"
	"github.com/jmoiron/sqlx"
	"github.com/prometheus/client_golang/prometheus"
	"github.com/signalfx/splunk-otel-go/instrumentation/github.com/jmoiron/sqlx/splunksqlx"
)

// ErrNotFound is returned when there is no product for a given ID.
var ErrNotFound = errors.New("not found")

// ErrDBConnection is returned when connection with the database fails.
var ErrDBConnection = errors.New("database connection error")

var baseQuery = "SELECT product.product_id AS id, product.name, product.description, product.price, product.count, product.image_url, GROUP_CONCAT(tag.name) AS tag_name FROM product JOIN product_tag ON product.product_id=product_tag.product_id JOIN tag ON product_tag.tag_id=tag.tag_id"

type mySQLRepository struct {
	db       *sqlx.DB
	readerDb *sqlx.DB
}

// credentialCache fetches and caches DB credentials from Secrets Manager with a TTL.
type credentialCache struct {
	client   *secretsmanager.Client
	secretId string

	mu       sync.Mutex
	username string
	password string
	expiry   time.Time
}

const credentialCacheTTL = 5 * time.Minute

// get returns cached credentials, refreshing from Secrets Manager if expired.
func (c *credentialCache) get(ctx context.Context) (string, string, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if time.Now().Before(c.expiry) {
		return c.username, c.password, nil
	}

	username, password, err := fetchCredentials(ctx, c.client, c.secretId)
	if err != nil {
		// If we have stale credentials, return them rather than failing
		if c.username != "" {
			log.Printf("Warning: failed to refresh credentials, using cached: %v", err)
			return c.username, c.password, nil
		}
		return "", "", err
	}

	c.username = username
	c.password = password
	c.expiry = time.Now().Add(credentialCacheTTL)
	return username, password, nil
}

// fetchCredentials retrieves username/password from a Secrets Manager secret.
func fetchCredentials(ctx context.Context, client *secretsmanager.Client, secretId string) (string, string, error) {
	out, err := client.GetSecretValue(ctx, &secretsmanager.GetSecretValueInput{
		SecretId: &secretId,
	})
	if err != nil {
		return "", "", fmt.Errorf("GetSecretValue(%s): %w", secretId, err)
	}

	var secret struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	if err := json.Unmarshal([]byte(*out.SecretString), &secret); err != nil {
		return "", "", fmt.Errorf("unmarshal secret: %w", err)
	}
	return secret.Username, secret.Password, nil
}

func newMySQLRepository(cfg config.DatabaseConfiguration) (Repository, error) {
	if cfg.CredentialsSecretId != "" {
		return newMySQLRepositoryWithSecretsManager(cfg)
	}

	connectionString := fmt.Sprintf("%s:%s@tcp(%s)/%s?timeout=%ds", cfg.User, cfg.Password, cfg.Endpoint, cfg.Name, cfg.ConnectTimeout)

	if cfg.Migrate {
		err := migrateMySQL(connectionString, cfg.MigrationsPath)
		if err != nil {
			log.Println("Error: Failed to run migration", err)
			return nil, err
		}
		log.Printf("Schema migration applied")
	} else {
		log.Printf("Skipping schema migration")
	}

	var readerDb *sqlx.DB

	db, err := createConnection(cfg.Endpoint, cfg.User, cfg.Password, cfg.Name, cfg.ConnectTimeout)
	if err != nil {
		log.Println("Error: Unable to connect to database", err)
		return nil, err
	}

	if len(cfg.ReadEndpoint) > 0 {
		readerDb, err = createConnection(cfg.ReadEndpoint, cfg.User, cfg.Password, cfg.Name, cfg.ConnectTimeout)
		if err != nil {
			log.Println("Error: Unable to connect to reader database", err)
			return nil, err
		}
	} else {
		readerDb = db
	}

	return &mySQLRepository{
		db:       db,
		readerDb: readerDb,
	}, nil
}

func newMySQLRepositoryWithSecretsManager(cfg config.DatabaseConfiguration) (Repository, error) {
	ctx := context.Background()

	awsCfg, err := awsconfig.LoadDefaultConfig(ctx)
	if err != nil {
		return nil, fmt.Errorf("load AWS config: %w", err)
	}

	smClient := secretsmanager.NewFromConfig(awsCfg)
	cache := &credentialCache{
		client:   smClient,
		secretId: cfg.CredentialsSecretId,
	}

	// Fetch initial credentials for migration and connectivity check
	username, password, err := cache.get(ctx)
	if err != nil {
		return nil, fmt.Errorf("fetch initial credentials: %w", err)
	}
	log.Printf("Fetched DB credentials from Secrets Manager")

	connectionString := fmt.Sprintf("%s:%s@tcp(%s)/%s?timeout=%ds", username, password, cfg.Endpoint, cfg.Name, cfg.ConnectTimeout)

	if cfg.Migrate {
		err := migrateMySQL(connectionString, cfg.MigrationsPath)
		if err != nil {
			log.Println("Error: Failed to run migration", err)
			return nil, err
		}
		log.Printf("Schema migration applied")
	} else {
		log.Printf("Skipping schema migration")
	}

	db, err := createConnectionWithBeforeConnect(cfg.Endpoint, cfg.Name, cfg.ConnectTimeout, cache)
	if err != nil {
		log.Println("Error: Unable to connect to database", err)
		return nil, err
	}

	var readerDb *sqlx.DB
	if len(cfg.ReadEndpoint) > 0 {
		readerDb, err = createConnectionWithBeforeConnect(cfg.ReadEndpoint, cfg.Name, cfg.ConnectTimeout, cache)
		if err != nil {
			log.Println("Error: Unable to connect to reader database", err)
			return nil, err
		}
	} else {
		readerDb = db
	}

	return &mySQLRepository{
		db:       db,
		readerDb: readerDb,
	}, nil
}

// createConnectionWithBeforeConnect creates a *sqlx.DB that refreshes credentials
// from Secrets Manager via a BeforeConnect hook on every new underlying connection.
func createConnectionWithBeforeConnect(endpoint, name string, timeout int, cache *credentialCache) (*sqlx.DB, error) {
	log.Printf("Connecting to %s/%s?timeout=%ds (with BeforeConnect)", endpoint, name, timeout)

	mysqlCfg, err := mysql.ParseDSN(fmt.Sprintf("placeholder:placeholder@tcp(%s)/%s?timeout=%ds", endpoint, name, timeout))
	if err != nil {
		return nil, fmt.Errorf("parse DSN: %w", err)
	}

	// BeforeConnect is called before each new connection; inject fresh credentials.
	mysqlCfg.Apply(mysql.BeforeConnect(func(ctx context.Context, cfg *mysql.Config) error {
		username, password, err := cache.get(ctx)
		if err != nil {
			return fmt.Errorf("refresh credentials: %w", err)
		}
		cfg.User = username
		cfg.Passwd = password
		return nil
	}))

	connector, err := mysql.NewConnector(mysqlCfg)
	if err != nil {
		return nil, fmt.Errorf("new connector: %w", err)
	}

	db := sqlx.NewDb(sql.OpenDB(connector), "mysql")

	if err := db.Ping(); err != nil {
		return nil, err
	}

	log.Printf("Connected")
	return db, nil
}

func createConnection(endpoint string, username string, password string, name string, timeout int) (*sqlx.DB, error) {
	log.Printf("Connecting to %s/%s?timeout=%ds", endpoint, name, timeout)

	connectionString := fmt.Sprintf("%s:%s@tcp(%s)/%s?timeout=%ds", username, password, endpoint, name, timeout)
	db, err := splunksqlx.Open("mysql", connectionString)
	if err != nil {
		return nil, err
	}

	err = db.Ping()
	if err != nil {
		return nil, err
	}

	log.Printf("Connected")

	return db, nil
}

func migrateMySQL(connectionString string, path string) error {
	log.Println("Running database migration...")

	m, err := migrate.New(
		"file://"+path,
		"mysql://"+connectionString,
	)
	if err != nil {
		log.Println("Error: Failed to prep migration", err)
		return err
	}

	err = m.Up()
	if err != nil {
		if err != migrate.ErrNoChange {
			log.Println("Error: Failed to apply migration", err)
			return err
		}
	}

	return nil
}

func (s *mySQLRepository) List(tags []string, order string, pageNum, pageSize int, ctx context.Context) ([]model.Product, error) {
	var products []model.Product
	query := baseQuery

	var args []interface{}

	for i, t := range tags {
		if i == 0 {
			query += " WHERE tag.name=?"
			args = append(args, t)
		} else {
			query += " OR tag.name=?"
			args = append(args, t)
		}
	}

	query += " GROUP BY id"

	if order != "" {
		query += " ORDER BY ?"
		args = append(args, order)
	}

	query += ";"

	err := s.readerDb.SelectContext(ctx, &products, query, args...)
	if err != nil {
		log.Println("database error", err)
		return []model.Product{}, ErrDBConnection
	}
	for i, s := range products {
		products[i].Tags = strings.Split(s.TagString, ",")
	}

	products = cut(products, pageNum, pageSize)

	return products, nil
}

func (s *mySQLRepository) Count(tags []string, ctx context.Context) (int, error) {
	query := "SELECT COUNT(DISTINCT product.product_id) FROM product JOIN product_tag ON product.product_id=product_tag.product_id JOIN tag ON product_tag.tag_id=tag.tag_id"

	var args []interface{}

	for i, t := range tags {
		if i == 0 {
			query += " WHERE tag.name=?"
			args = append(args, t)
		} else {
			query += " OR tag.name=?"
			args = append(args, t)
		}
	}

	query += ";"

	sel, err := s.readerDb.Prepare(query)

	if err != nil {
		log.Println("database error", err)
		return 0, ErrDBConnection
	}
	defer sel.Close()

	var count int
	err = sel.QueryRowContext(ctx, args...).Scan(&count)

	if err != nil {
		log.Println("database error", err)
		return 0, ErrDBConnection
	}

	return count, nil
}

func (s *mySQLRepository) Get(id string, ctx context.Context) (*model.Product, error) {
	query := baseQuery + " WHERE product.product_id =? GROUP BY product.product_id;"

	var product model.Product
	err := s.readerDb.GetContext(ctx, &product, query, id)
	if err != nil {
		log.Println("database error", err)
		return nil, ErrNotFound
	}

	product.Tags = strings.Split(product.TagString, ",")

	return &product, nil
}

func (s *mySQLRepository) Tags(ctx context.Context) ([]model.Tag, error) {
	var tags []model.Tag
	query := "SELECT name, display_name FROM tag;"
	rows, err := s.readerDb.QueryContext(ctx, query)
	if err != nil {
		log.Println("database error", err)
		return []model.Tag{}, ErrDBConnection
	}

	for rows.Next() {
		var tag model.Tag

		err = rows.Scan(&tag.Name, &tag.DisplayName)
		if err != nil {
			log.Println("Error reading tag row", err)
			continue
		}
		tags = append(tags, tag)
	}

	return tags, nil
}

func (s *mySQLRepository) Collector() prometheus.Collector {
	return sqlstats.NewStatsCollector("db", s.db)
}

func (s *mySQLRepository) ReaderCollector() prometheus.Collector {
	return sqlstats.NewStatsCollector("reader_db", s.db)
}

func cut(products []model.Product, pageNum, pageSize int) []model.Product {
	if pageNum == 0 || pageSize == 0 {
		return []model.Product{} // pageNum is 1-indexed
	}
	start := (pageNum * pageSize) - pageSize
	if start > len(products) {
		return []model.Product{}
	}
	end := (pageNum * pageSize)
	if end > len(products) {
		end = len(products)
	}
	return products[start:end]
}
