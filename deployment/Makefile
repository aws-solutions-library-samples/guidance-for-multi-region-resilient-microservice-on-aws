# Change these for your environment
ENV=
PRIMARY_REGION=us-east-1
STANDBY_REGION=us-west-2
####

####
# Generate Tag basedon git commit ref
#TAG=$(shell git rev-parse --short HEAD)
$(eval TAG:=$(shell LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 7))
# Generate Tag based on date hash
# TAG=$(date|sum|awk '{print $1}')

AWS_ACCOUNT_ID := $(shell aws sts get-caller-identity --output text|awk '{print $$1}')
AWS_PAGER:=''
.DEFAULT_GOAL := test-creds
MAKE=/usr/bin/make
DOCKER_BUILDKIT=0
COMPOSE_DOCKER_CLI_BUILD=0

ifeq ($(PRIMARY_ONLY),true)
PRIMARY_ONLY=true
else
PRIMARY_ONLY=false
endif
####

deploy-all: test-creds create-peer primary_infrastructure primary_ecs standby_infrastructure standby_ecs global_routing \
	canaries_primary canaries_standby failover_primary failover_standby client-primary client-standby restore-reconciliation monitoring \
	secrets-rotation chaos-engineering restart-ecs-services

deploy-primary: test-creds create-peer primary_infrastructure primary_ecs client-primary
	@echo "Deploy the Synthetic Canaries in ${PRIMARY_REGION}"
	$(eval result:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(PRIMARY_REGION) --query "Parameter.Value" --output text ))
	@aws cloudformation deploy --region ${PRIMARY_REGION} --template ./canaries.yaml \
	--stack-name canaries${ENV} --parameter-overrides Env=${ENV} RemoteRegion=${STANDBY_REGION} PrimaryOnly=true --capabilities CAPABILITY_IAM --s3-bucket $(result)

deploy: deploy-all
	@echo "*** Deployment Outputs ****"
	@echo ""
	@echo "Canaries:"
	@echo "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=${PRIMARY_REGION}#synthetics:canary/list"
	@echo "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=${STANDBY_REGION}#synthetics:canary/list"
	@echo ""
	@echo "Clients for in-VPC Browser:"
	@echo "https://${PRIMARY_REGION}.console.aws.amazon.com/systems-manager/fleet-manager/managed-nodes?region=${PRIMARY_REGION}"
	@echo "https://${STANDBY_REGION}.console.aws.amazon.com/systems-manager/fleet-manager/managed-nodes?region=${STANDBY_REGION}"
	@echo ""
	@echo "Administrator user passwords:"
	@echo "https://${PRIMARY_REGION}.console.aws.amazon.com/secretsmanager/secret?name=mr-app-windowspassword-${PRIMARY_REGION}${ENV}&region=${PRIMARY_REGION}"
	@echo "https://${STANDBY_REGION}.console.aws.amazon.com/secretsmanager/secret?name=mr-app-windowspassword-${STANDBY_REGION}${ENV}&region=${STANDBY_REGION}"
	@echo ""
	@echo "SSM Runbooks for failover execution:"
	@echo "https://${PRIMARY_REGION}.console.aws.amazon.com/systems-manager/documents"
	@echo "https://${STANDBY_REGION}.console.aws.amazon.com/systems-manager/documents"

create-peer:
	@echo "Verifying if the AWSServiceRoleForECS exists; if not; this will be created for you..."
	$(eval result:=$(shell aws iam list-roles --query "length(Roles[?RoleName=='AWSServiceRoleForECS'])"))
	@if [ "$(result)" -eq "0" ]; then \
		aws iam create-service-linked-role --aws-service-name ecs.amazonaws.com --no-cli-pager; \
	fi

	@echo "Deploying VPC Stack in ${PRIMARY_REGION}"
	@aws cloudformation deploy --template ./regionalVpc.yaml --region ${PRIMARY_REGION} \
	--stack-name baseVpc${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV} PrimaryOnly=true
	
	@if [ "$(PRIMARY_ONLY)" = "false" ];then \
		aws cloudformation deploy --template ./regionalVpc.yaml --region ${STANDBY_REGION} \
	--stack-name baseVpc${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV}; \
	fi

	@echo "create-peer done"

ecr-login:
	@echo "Verifying ECR Login in ${PRIMARY_REGION}"
	(aws ecr get-login-password --region $(PRIMARY_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(PRIMARY_REGION).amazonaws.com)
	@echo "Verifying ECR Login in ${STANDBY_REGION}"
	(aws ecr get-login-password --region $(STANDBY_REGION) | docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(STANDBY_REGION).amazonaws.com)

build-catalog-primary: primary_infrastructure ecr-login
	@echo "Build Catalog service Image and Push to ECR in ${PRIMARY_REGION}"
	@cd ../source/catalog/; docker build --platform linux/amd64 -t catalog${ENV}:${TAG} .
	docker tag catalog${ENV}:${TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/catalog${ENV}:${TAG}
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/catalog${ENV}:${TAG}

build-catalog-standby: standby_infrastructure ecr-login build-catalog-primary
	@echo "Push Catalog service Image to ECR in ${STANDBY_REGION}"
	docker tag catalog${ENV}:${TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/catalog${ENV}:${TAG}
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/catalog${ENV}:${TAG}

build-checkout-primary: primary_infrastructure ecr-login
	@echo "Build Checkout service image and Push to ECR in ${PRIMARY_REGION}"
	@cd ../source/checkout/; docker build --platform linux/amd64 -t checkout${ENV}:${TAG} .
	docker tag checkout${ENV}:${TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/checkout${ENV}:${TAG}
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/checkout${ENV}:${TAG}

build-checkout-standby: standby_infrastructure ecr-login build-checkout-primary
	@echo "Push Checkout service Image to ECR in ${STANDBY_REGION}"
	docker tag checkout${ENV}:${TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/checkout${ENV}:${TAG}
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/checkout${ENV}:${TAG}

build-ui-primary: primary_infrastructure ecr-login
	@echo "Build UI service image and Push to ECR in ${PRIMARY_REGION}"
	@cd ../source/ui/; docker build --platform linux/amd64 -t ui${ENV}:${TAG} .
	docker tag ui${ENV}:${TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/ui${ENV}:${TAG}
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/ui${ENV}:${TAG}

build-ui-standby: standby_infrastructure ecr-login build-ui-primary
	@echo "Push UI service Image to ECR in ${STANDBY_REGION}"
	docker tag ui${ENV}:${TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/ui${ENV}:${TAG}
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/ui${ENV}:${TAG}

build-carts-primary: primary_infrastructure ecr-login
	@echo "Build Carts service image and Push to ECR in ${PRIMARY_REGION}"
	@cd ../source/cart/; docker build --platform linux/amd64 -t carts${ENV}:${TAG} .
	docker tag carts${ENV}:${TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/carts${ENV}:${TAG}
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/carts${ENV}:${TAG}

build-carts-standby: standby_infrastructure ecr-login build-carts-primary
	@echo "Push Carts service Image to ECR in ${STANDBY_REGION}"
	docker tag carts${ENV}:${TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/carts${ENV}:${TAG}
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/carts${ENV}:${TAG}

build-assets-primary: primary_infrastructure ecr-login
	@echo "Build Assets service image and Push to ECR in ${PRIMARY_REGION}"
	@cd ../source/assets/; docker build --platform linux/amd64 -t assets${ENV}:${TAG} .
	docker tag assets${ENV}:${TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/assets${ENV}:${TAG}
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/assets${ENV}:${TAG}

build-assets-standby: standby_infrastructure ecr-login build-assets-primary
	@echo "Push Assets service Image to ECR in ${STANDBY_REGION}"
	docker tag assets${ENV}:${TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/assets${ENV}:${TAG}
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/assets${ENV}:${TAG}

build-orders-primary: primary_infrastructure ecr-login
	@echo "Build Orders service image and Push to ECR in ${PRIMARY_REGION}"
	@cd ../source/orders/; docker build --platform linux/amd64 -t orders${ENV}:${TAG} .
	docker tag orders${ENV}:${TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/orders${ENV}:${TAG}
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${PRIMARY_REGION}.amazonaws.com/orders${ENV}:${TAG}

build-orders-standby: standby_infrastructure ecr-login build-orders-primary
	@echo "Push Orders service Image to ECR in ${STANDBY_REGION}"
	docker tag orders${ENV}:${TAG} ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/orders${ENV}:${TAG}
	docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${STANDBY_REGION}.amazonaws.com/orders${ENV}:${TAG}

primary_infrastructure: create-peer
	@echo "Deploy Infrastructure resources in ${PRIMARY_REGION}"
	@aws cloudformation deploy --template ./regionalBaseInfra.yaml --region ${PRIMARY_REGION} \
	--stack-name baseInfra${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV} KmsKey=retail-store-ar${ENV} PrimaryOnly=${PRIMARY_ONLY}

primary_ecs: build-catalog-primary build-checkout-primary build-ui-primary build-carts-primary build-assets-primary build-orders-primary primary_region_catalog-db primary_region_orders-db carts-db
	@echo "Deploy ECS Services in ${PRIMARY_REGION}"
	@aws cloudformation deploy --template ./ecs.yaml --region ${PRIMARY_REGION} \
	--stack-name apps${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV} Tag=${TAG} KmsKey=retail-store-ar${ENV}

standby_infrastructure: create-peer
	@echo "Deploy Infrastructure resources in ${STANDBY_REGION}"
	@aws cloudformation deploy --template ./regionalBaseInfra.yaml --region ${STANDBY_REGION} \
	--stack-name baseInfra${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV} KmsKey=retail-store-ar${ENV}

standby_ecs: build-catalog-standby build-checkout-standby build-ui-standby build-carts-standby build-assets-standby build-orders-standby standby_region_catalog-db standby_region_orders-db
	@echo "Deploy ECS Services in ${STANDBY_REGION}"
	@aws cloudformation deploy --template ./ecs.yaml --region ${STANDBY_REGION} \
	--stack-name apps${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV} Tag=${TAG} KmsKey=retail-store-ar${ENV}

global_routing: standby_ecs primary_ecs
	@echo "Deploy the Global Routing layer"
	@aws cloudformation deploy --region ${PRIMARY_REGION} --template ./globalRouting.yaml \
	--stack-name gr${ENV} --capabilities CAPABILITY_NAMED_IAM --parameter-overrides DomainName=demo${ENV}.io Env=${ENV} KmsKey=retail-store-ar${ENV}

canaries_primary: global_routing
	@echo "Deploy the Synthetic Canaries in ${PRIMARY_REGION}"
	$(eval result:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(PRIMARY_REGION) --query "Parameter.Value" --output text ))
	@aws cloudformation deploy --region ${PRIMARY_REGION} --template ./canaries.yaml \
	--stack-name canaries${ENV} --parameter-overrides Env=${ENV} RemoteRegion=${STANDBY_REGION} --capabilities CAPABILITY_IAM --s3-bucket $(result)
canaries_standby: global_routing
	@echo "Deploy the Synthetic Canaries in ${STANDBY_REGION}"
	$(eval result:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(STANDBY_REGION) --query "Parameter.Value" --output text ))
	@aws cloudformation deploy --region ${STANDBY_REGION} --template ./canaries.yaml \
	--stack-name canaries${ENV} --parameter-overrides Env=${ENV} RemoteRegion=${PRIMARY_REGION} --capabilities CAPABILITY_IAM --s3-bucket $(result)

failover_primary: global_routing
	@echo "Deploy the Regional Failover runbook resources in ${PRIMARY_REGION}"
	@aws cloudformation deploy --region ${PRIMARY_REGION} --template ./failover.yaml \
	--stack-name failover${ENV} --parameter-overrides Env=${ENV} RemoteRegion=${STANDBY_REGION} --capabilities CAPABILITY_IAM
failover_standby: global_routing
	@echo "Deploy the Regional Failover runbook resources in ${STANDBY_REGION}"
	@aws cloudformation deploy --region ${STANDBY_REGION} --template ./failover.yaml \
	--stack-name failover${ENV} --parameter-overrides Env=${ENV} RemoteRegion=${PRIMARY_REGION} --capabilities CAPABILITY_IAM

primary_region_catalog-db: primary_infrastructure
	@echo "Creating Catalog service Aurora MySql database in ${PRIMARY_REGION}..."
	@aws cloudformation deploy --template ./database/aurora/aurora-global-primary-cluster.yml \
	--region ${PRIMARY_REGION} --stack-name catalog-db-stack${ENV} --capabilities CAPABILITY_IAM \
	--parameter-overrides Env=${ENV} NamingPrefix=catalog DatabaseName=catalog KmsKey=retail-store-ar${ENV}

standby_region_catalog-db: standby_infrastructure primary_region_catalog-db
	$(eval result:=$(shell aws ssm get-parameter --name catalog-global-db-cluster-CredentialSecretArn$(ENV) --region $(PRIMARY_REGION) --query "Parameter.Value" --output text|sed s/$(PRIMARY_REGION)/$(STANDBY_REGION)/g ))
	@echo "Creating Catalog service Aurora MySql database in ${STANDBY_REGION}..."
	@aws cloudformation deploy --template ./database/aurora/aurora-global-standby-cluster.yml \
	--region ${STANDBY_REGION} --stack-name catalog-db-stack${ENV} --capabilities CAPABILITY_IAM \
	--parameter-overrides Env=${ENV} NamingPrefix=catalog DBSecretArn=${result} DatabaseName=catalog KmsKey=retail-store-ar${ENV}

primary_region_orders-db: primary_infrastructure
	@echo "Creating Orders service Aurora MySql database in ${PRIMARY_REGION}..."
	@aws cloudformation deploy --template ./database/aurora/aurora-global-primary-cluster.yml \
	--region ${PRIMARY_REGION} --stack-name orders-db-stack${ENV} --capabilities CAPABILITY_IAM \
	--parameter-overrides Env=${ENV} NamingPrefix=orders DatabaseName=orders KmsKey=retail-store-ar${ENV}

standby_region_orders-db: standby_infrastructure primary_region_orders-db
	$(eval result:=$(shell aws ssm get-parameter --name orders-global-db-cluster-CredentialSecretArn$(ENV) --region $(PRIMARY_REGION) --query "Parameter.Value" --output text|sed s/$(PRIMARY_REGION)/$(STANDBY_REGION)/g ))
	@echo "Creating Orders service Aurora MySql database in ${STANDBY_REGION}..."
	@aws cloudformation deploy --template ./database/aurora/aurora-global-standby-cluster.yml \
	--region ${STANDBY_REGION} --stack-name orders-db-stack${ENV} --capabilities CAPABILITY_IAM \
	--parameter-overrides Env=${ENV} NamingPrefix=orders DBSecretArn=${result} DatabaseName=orders KmsKey=retail-store-ar${ENV}

carts-db: primary_infrastructure
	@echo "Verifying if the AWSServiceRoleForDynamoDBReplication exists; if not; this will be created for you..."
	$(eval resultDDB:=$(shell aws iam list-roles --query "length(Roles[?RoleName=='AWSServiceRoleForDynamoDBReplication'])"))
	@if [ "$(resultDDB)" -eq "0" ]; then \
    		aws iam create-service-linked-role --aws-service-name replication.dynamodb.amazonaws.com --no-cli-pager; \
    fi
	@echo "Creating Carts service DynamoDB Global Table in ${PRIMARY_REGION} and ${STANDBY_REGION}..."
	@aws cloudformation deploy --template ./database/dynamodb/global-table.yml \
	--region ${PRIMARY_REGION} --stack-name carts-db-stack${ENV} --capabilities CAPABILITY_IAM \
	--parameter-overrides Env=${ENV} NamingPrefix=carts KmsKey=retail-store-ar${ENV}

client-primary: primary_infrastructure
	@echo "Deploy the Windows Client in the Primary Region"
	$(eval subnet:=$(shell aws ssm get-parameter --name Subnet1$(ENV) --region $(PRIMARY_REGION) --query "Parameter.Value" --output text))
	$(eval vpc:=$(shell aws secretsmanager get-secret-value --secret-id VpcId-$(PRIMARY_REGION)$(ENV) --region $(PRIMARY_REGION) --query "SecretString" --output text))
	@echo "Creating Windows client for testing purposes in ${PRIMARY_REGION}"
	@aws cloudformation deploy --template ./windows.yaml --parameter-overrides Env=${ENV} SubnetId=${subnet} VpcId=${vpc} KmsKey=retail-store-ar${ENV} --region ${PRIMARY_REGION} --capabilities CAPABILITY_IAM --stack-name client${ENV}

client-standby: standby_infrastructure
	@echo "Deploy the Windows Client in the Standby Region"
	$(eval subnet:=$(shell aws ssm get-parameter --name Subnet1$(ENV) --region $(STANDBY_REGION) --query "Parameter.Value" --output text))
	$(eval vpc:=$(shell aws secretsmanager get-secret-value --secret-id VpcId-$(STANDBY_REGION)$(ENV) --region $(STANDBY_REGION) --query "SecretString" --output text))
	@echo "Creating Windows client for testing purposes in ${STANDBY_REGION}"
	@aws cloudformation deploy --template ./windows.yaml --parameter-overrides Env=${ENV} SubnetId=${subnet} VpcId=${vpc} KmsKey=retail-store-ar${ENV} --region ${STANDBY_REGION} --capabilities CAPABILITY_IAM --stack-name client${ENV}

restore-reconciliation: primary_infrastructure primary_region_orders-db standby_infrastructure standby_region_orders-db
	@echo "Creating IAM Role for restore-reconcliation"
	@aws cloudformation deploy --template ./database/crdr-reconciliation/src/crdr-roles.yaml --parameter-overrides KmsKey=retail-store-ar${ENV} Env=${ENV} --capabilities CAPABILITY_NAMED_IAM --stack-name crdr-roles${ENV}  --region ${PRIMARY_REGION}
	@echo "Creating SSM automation runbook in ${PRIMARY_REGION}"
	@aws cloudformation deploy --template ./database/crdr-reconciliation/src/cross-region-orders-db-ssm.yaml --parameter-overrides Env=${ENV} --capabilities CAPABILITY_NAMED_IAM --stack-name crdr-orders-ssm${ENV} --region ${PRIMARY_REGION}

	@echo "Creating reconciliation resources in ${STANDBY_REGION}"
	@echo "Step 1:Building Lambda Layers"
	./build-lambda-layer.sh
	@echo "Step 2:Deploying Lambda and SSM Runbook"
	$(eval result:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(STANDBY_REGION) --query "Parameter.Value" --output text ))
	@aws cloudformation package --template-file ./database/crdr-reconciliation/src/restore-reconcile-orders-ssm.yaml --region ${STANDBY_REGION} --s3-bucket $(result) --output-template-file ./database/crdr-reconciliation/src/out.yaml
	@aws cloudformation deploy --template-file ./database/crdr-reconciliation/src/out.yaml --stack-name reconciliation-orders-ssm${ENV} --region ${STANDBY_REGION} --capabilities CAPABILITY_NAMED_IAM --parameter-overrides Env=${ENV}

monitoring: restore-reconciliation
	@echo "Deploy the Monitoring Dashboard"
	@aws cloudformation deploy --region ${PRIMARY_REGION} --template ./monitoring.yml \
	--stack-name monitoring${ENV} --capabilities CAPABILITY_NAMED_IAM --parameter-overrides PrimaryRegion=${PRIMARY_REGION} Env=${ENV} SecondaryRegion=${STANDBY_REGION}

secrets-rotation: primary_region_orders-db primary_region_catalog-db
	@echo "Creating secrets rotation resources in ${PRIMARY_REGION}"
	@echo "Step 1:Building Lambda Layers"
	./database/secrets-rotation/build-lambda-layer.sh
	@echo "Step 2:Deploying Lambda"
	$(eval result:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(PRIMARY_REGION) --query "Parameter.Value" --output text ))
	@aws cloudformation package --template-file ./database/secrets-rotation/src/secrets-rotation.yaml --region ${PRIMARY_REGION} --s3-bucket $(result) --output-template-file ./database/secrets-rotation/src/out.yaml
	@aws cloudformation deploy --template-file ./database/secrets-rotation/src/out.yaml --stack-name secrets-rotation${ENV} --region ${PRIMARY_REGION} --capabilities CAPABILITY_NAMED_IAM --parameter-overrides Env=${ENV} OrdersDBCredentialsSecretId=mr-app/orders-global-db-cluster-UserCredentials${ENV} CatalogDBCredentialsSecretId=mr-app/catalog-global-db-cluster-UserCredentials${ENV}

restart-ecs-services:
	@echo "Restarting ECS Services"
	@if [ -z "${ENV}" ]; then \
		./restart-services.sh --services catalog,orders; \
	else \
		./restart-services.sh --env ${ENV} --services catalog,orders; \
	fi

chaos-engineering: create-peer
	@echo "Creating chaos experiments in ${PRIMARY_REGION}"
	$(eval result:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(PRIMARY_REGION) --query "Parameter.Value" --output text ))
	@aws cloudformation deploy --template-file ./chaos/multi-region-scenario.yaml --stack-name chaos${ENV} --region ${PRIMARY_REGION} --capabilities CAPABILITY_NAMED_IAM --parameter-overrides Env=${ENV} Region=${STANDBY_REGION}
	@echo "Creating chaos experiments in ${STANDBY_REGION}"
	$(eval result:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(STANDBY_REGION) --query "Parameter.Value" --output text ))
	@aws cloudformation deploy --template-file ./chaos/multi-region-scenario.yaml --stack-name chaos${ENV} --region ${STANDBY_REGION} --capabilities CAPABILITY_NAMED_IAM --parameter-overrides Env=${ENV} Region=${PRIMARY_REGION}

clean:
	@echo "To remove all stacks deployed by this solution, run 'make destroy-all'"

test-creds:
	@echo "Current AWS session:"
	@aws sts get-caller-identity

destroy-all: destroy-peer destroy-restore-reconciliation-ssm destroy-chaos-engineering
	@echo "Removed all cloudformation stacks!!!"

destroy-chaos-engineering:
	@echo "Deleting Chaos Engineering stacks"
	@aws cloudformation delete-stack --stack-name chaos${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation delete-stack --stack-name chaos${ENV} --region ${STANDBY_REGION}

destroy-secrets-rotation:
	@echo "Deleting secrets rotation stack"
	@aws cloudformation delete-stack --stack-name secrets-rotation${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name secrets-rotation${ENV} --region ${PRIMARY_REGION}

destroy-monitoring:
	@echo "Deleting monitoring stack"
	@aws cloudformation delete-stack --stack-name monitoring${ENV} --region ${PRIMARY_REGION}

destroy-restore-reconciliation-ssm: destroy-monitoring

	echo "Deleting Aurora database instances and clusters in ${STANDBY_REGION} region..."
	./clean-up-aurora-cluster.sh ${STANDBY_REGION}
	@echo "Deleting SSM automation runbook in ${PRIMARY_REGION}"
	@aws cloudformation delete-stack --stack-name crdr-orders-ssm${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation delete-stack --stack-name reconciliation-orders-ssm${ENV} --region ${STANDBY_REGION}	
	@aws cloudformation wait stack-delete-complete --stack-name reconciliation-orders-ssm${ENV} --region ${STANDBY_REGION}
	@echo "Deleting IAM Role for restore-reconcliation"
	@aws cloudformation delete-stack --stack-name crdr-roles${ENV} --region ${PRIMARY_REGION}

destroy-ecr-primary: destroy-apps-primary
	@echo "Deleting ECR Repos..."
	@aws ecr delete-repository --force --repository-name catalog${ENV} --region $(PRIMARY_REGION) --no-cli-pager || true
	@aws ecr delete-repository --force --repository-name checkout${ENV} --region $(PRIMARY_REGION) --no-cli-pager || true
	@aws ecr delete-repository --force --repository-name ui${ENV} --region $(PRIMARY_REGION) --no-cli-pager || true
	@aws ecr delete-repository --force --repository-name carts${ENV} --region $(PRIMARY_REGION) --no-cli-pager || true
	@aws ecr delete-repository --force --repository-name assets${ENV} --region $(PRIMARY_REGION) --no-cli-pager || true
	@aws ecr delete-repository --force --repository-name orders${ENV} --region $(PRIMARY_REGION) --no-cli-pager || true

destroy-ecr-standby: destroy-apps-standby
	@echo "Deleting ECR Repos..."
	@aws ecr delete-repository --force --repository-name catalog${ENV} --region $(STANDBY_REGION) --no-cli-pager || true
	@aws ecr delete-repository --force --repository-name checkout${ENV} --region $(STANDBY_REGION) --no-cli-pager || true
	@aws ecr delete-repository --force --repository-name ui${ENV} --region $(STANDBY_REGION) --no-cli-pager || true
	@aws ecr delete-repository --force --repository-name carts${ENV} --region $(STANDBY_REGION) --no-cli-pager || true
	@aws ecr delete-repository --force --repository-name assets${ENV} --region $(STANDBY_REGION) --no-cli-pager || true
	@aws ecr delete-repository --force --repository-name orders${ENV} --region $(STANDBY_REGION) --no-cli-pager || true

destroy-global_routing: destroy-canaries-standby destroy-canaries-primary destroy-failover-standby destroy-failover-primary destroy-restore-reconciliation-ssm
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
	
destroy-apps-primary: destroy-global_routing
	@echo "Cleaning up S3 Buckets in ${PRIMARY_REGION}..."
	$(eval result:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(PRIMARY_REGION) --query "Parameter.Value" --output text ))
	./cleanup.sh $(result)

	@echo "Deleting applications in ${PRIMARY_REGION}..."
	@aws cloudformation delete-stack --stack-name apps${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name apps${ENV} --region ${PRIMARY_REGION}

destroy-apps-standby: destroy-global_routing
	@echo "Cleaning up S3 Buckets in ${STANDBY_REGION}..."
	$(eval result:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(STANDBY_REGION) --query "Parameter.Value" --output text ))
	./cleanup.sh $(result)
	
	@echo "Deleting applications in ${STANDBY_REGION}..."
	@aws cloudformation delete-stack --stack-name apps${ENV} --region ${STANDBY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name apps${ENV} --region ${STANDBY_REGION}

destroy-infra: destroy-ecr-standby destroy-ecr-primary destroy-databases-standby destroy-databases-primary destroy-client-primary destroy-client-standby
	@echo "Deleting networking resources in ${STANDBY_REGION}..."
	@aws cloudformation delete-stack --stack-name baseInfra${ENV} --region ${STANDBY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name baseInfra${ENV} --region ${STANDBY_REGION}
	@echo "Deleting networking resources in ${PRIMARY_REGION}..."
	@aws cloudformation delete-stack --stack-name baseInfra${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name baseInfra${ENV} --region ${PRIMARY_REGION}

destroy-canaries-standby:
	@echo "Deleting canaries in ${STANDBY_REGION}..."
	@aws cloudformation delete-stack --stack-name canaries${ENV} --region ${STANDBY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name canaries${ENV} --region ${STANDBY_REGION}

destroy-canaries-primary:
	@echo "Deleting canaries in ${PRIMARY_REGION}..."
	@aws cloudformation delete-stack --stack-name canaries${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name canaries${ENV} --region ${PRIMARY_REGION}

destroy-failover-standby:
	@echo "Deleting failover in ${STANDBY_REGION}..."
	@aws cloudformation delete-stack --stack-name failover${ENV} --region ${STANDBY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name failover${ENV} --region ${STANDBY_REGION}

destroy-failover-primary:
	@echo "Deleting failover in ${PRIMARY_REGION}..."
	@aws cloudformation delete-stack --stack-name failover${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name failover${ENV} --region ${PRIMARY_REGION}

destroy-databases-primary: destroy-secrets-rotation destroy-apps-primary destroy-databases-standby
	@echo "Deleting databases in ${PRIMARY_REGION}..."
	@aws cloudformation delete-stack --stack-name catalog-db-stack${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation delete-stack --stack-name orders-db-stack${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation delete-stack --stack-name carts-db-stack${ENV} --region ${PRIMARY_REGION}

	@aws cloudformation wait stack-delete-complete --stack-name catalog-db-stack${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name orders-db-stack${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name carts-db-stack${ENV} --region ${PRIMARY_REGION}

destroy-databases-standby: destroy-apps-standby 
	@echo "Deleting databases in ${STANDBY_REGION}..."
	@aws cloudformation delete-stack --stack-name catalog-db-stack${ENV} --region ${STANDBY_REGION}
	@aws cloudformation delete-stack --stack-name orders-db-stack${ENV} --region ${STANDBY_REGION}
	
	@aws cloudformation wait stack-delete-complete --stack-name catalog-db-stack${ENV} --region ${STANDBY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name orders-db-stack${ENV} --region ${STANDBY_REGION}

destroy-client-primary:
	@echo "Deleting client in ${PRIMARY_REGION}"
	@aws cloudformation delete-stack --stack-name client${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name client${ENV} --region ${PRIMARY_REGION}
	
destroy-client-standby:
	@echo "Deleting client in ${STANDBY_REGION}"
	@aws cloudformation delete-stack --stack-name client${ENV} --region ${STANDBY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name client${ENV} --region ${STANDBY_REGION}
