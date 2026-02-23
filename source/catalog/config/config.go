package config

// Configuration exported
type AppConfiguration struct {
	Port     int `env:"PORT,default=8080"`
	Database DatabaseConfiguration
}

// DatabaseConfiguration exported
type DatabaseConfiguration struct {
	Type           string `env:"DB_TYPE,default=mysql"`
	Endpoint       string `env:"DB_ENDPOINT,default=catalog-db:3306"`
	ReadEndpoint   string `env:"DB_READ_ENDPOINT"`
	Name           string `env:"DB_NAME,default=sampledb"`
	User           string `env:"DB_USER,default=catalog_user"`
	Password             string `env:"DB_PASSWORD"`
	CredentialsSecretId  string `env:"DB_CREDENTIALS_SECRET_ID"`
	Migrate        bool   `env:"DB_MIGRATE,default=true"`
	ConnectTimeout int    `env:"DB_CONNECT_TIMEOUT,default=5"`
	MigrationsPath string `env:"DB_MIGRATIONS_PATH,default=db/migrations"`
}
