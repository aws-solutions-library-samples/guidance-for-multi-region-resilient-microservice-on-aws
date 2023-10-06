# Change these for your environment
ENV="-dev0"
PRIMARY_REGION=us-east-1
STANDBY_REGION=us-west-2
####

####
AWS_ACCOUNT_ID := $(shell aws sts get-caller-identity --output text|awk '{print $$1}')
AWS_PAGER:=''
.DEFAULT_GOAL := test-creds
MAKE=/usr/bin/make
DOCKER_BUILDKIT=0
COMPOSE_DOCKER_CLI_BUILD=0
####
deploy: deploy-ecs
deploy-ecs: test-creds create-peer primary_infrastructure primary_ecs standby_infrastructure standby_ecs global_routing canaries_primary canaries_standby
deploy-ecs-primary: test-creds primary_infrastructure primary_ecs

create-peer:
	@aws cloudformation deploy --template ./regionalVpc.yaml --region ${PRIMARY_REGION} \
	--stack-name baseVpc${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV}
	@aws cloudformation deploy --template ./regionalVpc.yaml --region ${STANDBY_REGION} \
	--stack-name baseVpc${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV}

build-catalog-primary: primary_infrastructure
	@cd ../source/catalog/; docker build -t catalog${ENV} .
	(aws ecr get-login-password --region $(PRIMARY_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(PRIMARY_REGION).amazonaws.com)
	docker tag catalog${ENV}:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/catalog${ENV}:latest
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/catalog${ENV}:latest

build-catalog-standby: standby_infrastructure
	@cd ../source/catalog/; docker build -t catalog${ENV} .
	(aws ecr get-login-password --region $(STANDBY_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(STANDBY_REGION).amazonaws.com)
	docker tag catalog${ENV}:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/catalog${ENV}:latest
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/catalog${ENV}:latest

primary_infrastructure: create-peer
	@aws cloudformation deploy --template ./regionalBaseInfra.yaml --region ${PRIMARY_REGION} \
	--stack-name baseInfra${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV}

primary_ecs: primary_infrastructure build-catalog-primary build-ui-primary primary_region_catalog-db primary_region_orders-db
	@aws cloudformation deploy --template ./ecs.yaml --region ${PRIMARY_REGION} \
	--stack-name apps${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV}

standby_infrastructure: create-peer
	@aws cloudformation deploy --template ./regionalBaseInfra.yaml --region ${STANDBY_REGION} \
	--stack-name baseInfra${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV}

standby_ecs: standby_infrastructure build-catalog-standby build-ui-standby standby_region_catalog-db standby_region_orders-db
	@aws cloudformation deploy --template ./ecs.yaml --region ${STANDBY_REGION} \
	--stack-name apps${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV}

global_routing: standby_ecs primary_ecs
	@aws cloudformation deploy --region ${PRIMARY_REGION} --template ./globalRouting.yaml \
	--stack-name gr${ENV} --parameter-overrides DomainName=demo${ENV}.io Env=${ENV} 

canaries_primary: global_routing
	@aws cloudformation deploy --region ${PRIMARY_REGION} --template ./canaries.yaml \
	--stack-name canaries${ENV} --parameter-overrides Env=${ENV} RemoteRegion=${STANDBY_REGION} --capabilities CAPABILITY_IAM 
canaries_standby: global_routing
	@aws cloudformation deploy --region ${STANDBY_REGION} --template ./canaries.yaml \
	--stack-name canaries${ENV} --parameter-overrides Env=${ENV} RemoteRegion=${PRIMARY_REGION} --capabilities CAPABILITY_IAM

primary_region_catalog-db:
	@aws cloudformation deploy --template ./datastores/aurora/aurora-global-primary-cluster.yml \
	--region ${PRIMARY_REGION} --stack-name catalog-db-stack-${ENV} --capabilities CAPABILITY_IAM \
	--parameter-overrides Env=${ENV} NamingPrefix=catalog

standby_region_catalog-db:
	@aws cloudformation deploy --template ./datastores/aurora/aurora-global-standby-cluster.yml \
	--region ${STANDBY_REGION} --stack-name catalog-db-stack-${ENV} --capabilities CAPABILITY_IAM \
	--parameter-overrides Env=${ENV} NamingPrefix=catalog

primary_region_orders-db:
	@aws cloudformation deploy --template ./datastores/aurora/aurora-global-primary-cluster.yml \
	--region ${PRIMARY_REGION} --stack-name orders-db-stack-${ENV} --capabilities CAPABILITY_IAM \
	--parameter-overrides Env=${ENV} NamingPrefix=orders

standby_region_orders-db:
	@aws cloudformation deploy --template ./datastores/aurora/aurora-global-standby-cluster.yml \
	--region ${STANDBY_REGION} --stack-name orders-db-stack-${ENV} --capabilities CAPABILITY_IAM \
	--parameter-overrides Env=${ENV} NamingPrefix=orders

build-ui-primary: primary_infrastructure
	@cd ../source/ui/; docker build -t ui${ENV} .
	(aws ecr get-login-password --region $(PRIMARY_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(PRIMARY_REGION).amazonaws.com)
	docker tag ui${ENV}:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/ui${ENV}:latest
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/ui${ENV}:latest

build-ui-standby: standby_infrastructure
	@cd ../source/ui/; docker build -t ui${ENV} .
	(aws ecr get-login-password --region $(STANDBY_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(STANDBY_REGION).amazonaws.com)
	docker tag ui${ENV}:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/ui${ENV}:latest
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/ui${ENV}:latest

clean:
	@echo "To remove all stacks deployed by this solution, run 'make destroy-all'"

test-creds:
	@echo "Current AWS session:"
	@aws sts get-caller-identity

destroy-all: destroy-global_routing destroy-apps destroy-ecr destroy-infra destroy-peer 
	@echo "Removed all cloudformation stacks!!!"

destroy-ecr:
	@echo "Deleting ECR Repos..."
	@aws ecr delete-repository --force --repository-name catalog${ENV} --region $(PRIMARY_REGION) --no-cli-pager || true
	@aws ecr delete-repository --force --repository-name catalog${ENV} --region $(STANDBY_REGION) --no-cli-pager || true

destroy-global_routing: 
	@echo "Deleting global routing stack..."
	@aws cloudformation delete-stack --stack-name gr${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name gr${ENV} --region ${PRIMARY_REGION}
	
destroy-peer: destroy-peer_primary destroy-peer_standby 

destroy-peer_standby: destroy-infra
	@echo "Deleting ${STANDBY_REGION} VPC..."
	@aws cloudformation delete-stack --stack-name baseVpc${ENV} --region ${STANDBY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name baseVpc${ENV} --region ${STANDBY_REGION}

destroy-peer_primary: destroy-peer_standby
	@echo "Deleting ${PRIMARY_REGION} VPC..."
	@aws cloudformation delete-stack --stack-name baseVpc${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name baseVpc${ENV} --region ${PRIMARY_REGION}

destroy-apps: destroy-apps-primary destroy-apps-standby
	
destroy-apps-primary: destroy-global_routing
	@echo "Cleaning up S3 Buckets in ${PRIMARY_REGION}..."
	$(eval result:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(PRIMARY_REGION) --query "Parameter.Value" --output text ))
	./cleanup.sh $(result)

	@echo "Deleting canaries in ${PRIMARY_REGION}..."
	@aws cloudformation delete-stack --stack-name canaries${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name canaries${ENV} --region ${PRIMARY_REGION}

	@echo "Deleting applications in ${PRIMARY_REGION}..."
	@aws cloudformation delete-stack --stack-name apps${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name apps${ENV} --region ${PRIMARY_REGION}

destroy-apps-standby: destroy-global_routing
	@echo "Cleaning up S3 Buckets in ${STANDBY_REGION}..."
	$(eval result:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(STANDBY_REGION) --query "Parameter.Value" --output text ))
	./cleanup.sh $(result)
	
	@echo "Deleting canaries in ${STANDBY_REGION}..."
	@aws cloudformation delete-stack --stack-name canaries${ENV} --region ${STANDBY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name canaries${ENV} --region ${STANDBY_REGION}

	@echo "Deleting applications in ${STANDBY_REGION}..."
	@aws cloudformation delete-stack --stack-name apps${ENV} --region ${STANDBY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name apps${ENV} --region ${STANDBY_REGION}
destroy-infra: destroy-apps destroy-ecr
	@echo "Deleting networking resources in ${STANDBY_REGION}..."
	@aws cloudformation delete-stack --stack-name baseInfra${ENV} --region ${STANDBY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name baseInfra${ENV} --region ${STANDBY_REGION}
	@echo "Deleting networking resources in ${PRIMARY_REGION}..."
	@aws cloudformation delete-stack --stack-name baseInfra${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name baseInfra${ENV} --region ${PRIMARY_REGION}