/*
 * Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
 * SPDX-License-Identifier: MIT-0
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this
 * software and associated documentation files (the "Software"), to deal in the Software
 * without restriction, including without limitation the rights to use, copy, modify,
 * merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
 * INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
 * PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
 * HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
 * OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

package com.amazon.sample.orders.config.persistence;

import com.zaxxer.hikari.HikariDataSource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.orm.jpa.EntityManagerFactoryBuilder;
import org.springframework.context.annotation.*;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.orm.jpa.JpaTransactionManager;
import org.springframework.orm.jpa.LocalContainerEntityManagerFactoryBean;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.EnableTransactionManagement;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.dsql.DsqlUtilities;

import jakarta.persistence.EntityManagerFactory;
import javax.sql.DataSource;

@Configuration
@Profile("dsql")
@EnableTransactionManagement
@EnableJpaRepositories(
        basePackages = "com.amazon.sample.orders"
)
@Slf4j
public class DsqlDataSourceConfig {

    @Value("${spring.datasource.dsql.endpoint}")
    private String dsqlEndpoint;

    @Value("${spring.datasource.dsql.auth-hostname:#{null}}")
    private String dsqlAuthHostname;

    @Value("${spring.datasource.dsql.region}")
    private String dsqlRegion;

    private HikariDataSource hikariDataSource;

    @Primary
    @Bean
    public DataSource dataSource() {
        hikariDataSource = new HikariDataSource();
        hikariDataSource.setJdbcUrl("jdbc:postgresql://" + dsqlEndpoint + ":5432/postgres");
        hikariDataSource.setUsername("admin");
        hikariDataSource.setPassword(generateAuthToken());
        hikariDataSource.setDriverClassName("org.postgresql.Driver");
        hikariDataSource.setMaxLifetime(600000); // 10 minutes, well under 15 min token expiry
        return hikariDataSource;
    }

    @Primary
    @Bean
    public LocalContainerEntityManagerFactoryBean entityManagerFactory(
            EntityManagerFactoryBuilder builder,
            DataSource dataSource
    ) {
        return builder
                .dataSource(dataSource)
                .packages("com.amazon.sample.orders")
                .persistenceUnit("dsql")
                .build();
    }

    @Primary
    @Bean
    public PlatformTransactionManager transactionManager(EntityManagerFactory entityManagerFactory) {
        return new JpaTransactionManager(entityManagerFactory);
    }

    @Scheduled(fixedRate = 600000) // Refresh every 10 minutes
    public void refreshAuthToken() {
        if (hikariDataSource != null) {
            String newToken = generateAuthToken();
            hikariDataSource.setPassword(newToken);
            log.info("Refreshed DSQL auth token");
        }
    }

    private String generateAuthToken() {
        String hostname = (dsqlAuthHostname != null) ? dsqlAuthHostname : dsqlEndpoint;
        DsqlUtilities utilities = DsqlUtilities.builder()
                .region(Region.of(dsqlRegion))
                .credentialsProvider(DefaultCredentialsProvider.create())
                .build();
        return utilities.generateDbConnectAdminAuthToken(builder ->
                builder.hostname(hostname));
    }
}
