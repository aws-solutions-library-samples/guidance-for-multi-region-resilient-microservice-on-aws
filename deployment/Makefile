# Prerequisites:
# - kubectl
# - awscli


ENV="dev"
PRIMARY_REGION=us-east-1
STANDBY_REGION=us-west-2
EKSCLUSTERVERSION=1.27

.DEFAULT_GOAL := test-creds
MAKE=/usr/bin/make

build:

deploy: test-creds primary_region_infrastructure standby_region_infrastructure primary_region_catalog-db standby_region_catalog-db

primary_region_infrastructure:
	@aws cloudformation deploy --template ./regionalBaseInfra.yaml --region ${PRIMARY_REGION} \
	--stack-name baseInfra-${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV}
standby_region_infrastructure:
	@aws cloudformation deploy --template ./regionalBaseInfra.yaml --region ${STANDBY_REGION} \
	--stack-name baseInfra-${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV}
primary_region_catalog-db:
	@aws cloudformation deploy --template ./datastores/catalog/aurora-global-primary-cluster.yml \
	--region ${PRIMARY_REGION} --stack-name catalog-db-stack-${ENV} --capabilities CAPABILITY_IAM \
	--parameter-overrides Env=${ENV} NamingPrefix=catalog
standby_region_catalog-db:
	@aws cloudformation deploy --template ./datastores/catalog/aurora-global-standby-cluster.yml \
	--region ${STANDBY_REGION} --stack-name catalog-db-stack-${ENV} --capabilities CAPABILITY_IAM \
	--parameter-overrides Env=${ENV} NamingPrefix=catalog

clean:
	@echo "To remove all stacks deployed by this solution, run 'make destroy-all'"

test-creds:
	@echo "Current AWS session:"
	@aws sts get-caller-identity

destroy-all:
	@echo "Removing all cloudformation stacks!!!"
	@aws cloudformation delete-stack --stack-name baseInfra-${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name baseInfra-${ENV} --region ${PRIMARY_REGION}