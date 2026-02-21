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
CODEBUILD_PROJECT=mr-app-docker-build$(ENV)

ifeq ($(PRIMARY_ONLY),true)
PRIMARY_ONLY=true
else
PRIMARY_ONLY=false
endif
####

deploy-all: test-creds create-peer primary_infrastructure primary_ecs standby_infrastructure standby_ecs global_routing \
	canaries_primary canaries_standby region-switch client-primary client-standby restore-reconciliation monitoring \
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
	@echo "Region Switch Plan:"
	@echo "Use 'aws arc-region-switch start-plan-execution' to initiate failover"

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

####
# CodeBuild infrastructure and build targets
####

codebuild-infra: primary_infrastructure
	@echo "Deploying CodeBuild project in ${PRIMARY_REGION}"
	@aws cloudformation deploy --template ./codebuild.yaml --region ${PRIMARY_REGION} \
	--stack-name codebuild${ENV} --capabilities CAPABILITY_NAMED_IAM \
	--parameter-overrides Env=${ENV} PrimaryRegion=${PRIMARY_REGION} StandbyRegion=${STANDBY_REGION} KmsKey=retail-store-ar

# Internal helper: package source, upload to S3, trigger CodeBuild, poll until complete
# Usage: $(call codebuild-build,SERVICE_NAME,SOURCE_DIR)
define codebuild-build
	@echo "Packaging $(1) source from ../source/$(2)..."
	$(eval _BUCKET:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(PRIMARY_REGION) --query "Parameter.Value" --output text))
	@cd ../source/$(2) && zip -r -q /tmp/$(1)-source.zip . -x '*.git*'
	@echo "Uploading $(1) source to S3..."
	@aws s3 cp /tmp/$(1)-source.zip s3://$(_BUCKET)/codebuild/source.zip --region $(PRIMARY_REGION)
	@rm -f /tmp/$(1)-source.zip
	@echo "Starting CodeBuild for $(1) with tag ${TAG}..."
	$(eval _BUILD_ID:=$(shell aws codebuild start-build \
		--project-name $(CODEBUILD_PROJECT) \
		--source-type-override S3 \
		--source-location-override $(_BUCKET)/codebuild/source.zip \
		--environment-variables-override \
			name=SERVICE_NAME,value=$(1),type=PLAINTEXT \
			name=TAG,value=${TAG},type=PLAINTEXT \
			name=ENV_SUFFIX,value=${ENV},type=PLAINTEXT \
			name=PRIMARY_REGION,value=${PRIMARY_REGION},type=PLAINTEXT \
			name=STANDBY_REGION,value=${STANDBY_REGION},type=PLAINTEXT \
			name=PRIMARY_ONLY,value=${PRIMARY_ONLY},type=PLAINTEXT \
		--region $(PRIMARY_REGION) \
		--query 'build.id' --output text))
	@echo "Build started: $(_BUILD_ID)"
	@echo "Waiting for CodeBuild to complete..."
	@while true; do \
		STATUS=$$(aws codebuild batch-get-builds --ids $(_BUILD_ID) --region $(PRIMARY_REGION) --query 'builds[0].buildStatus' --output text 2>/dev/null || echo "POLL_ERROR"); \
		if [ "$$STATUS" = "SUCCEEDED" ]; then \
			echo "CodeBuild for $(1) completed successfully"; \
			break; \
		elif [ "$$STATUS" = "IN_PROGRESS" ]; then \
			echo "  ...still building $(1)"; \
			sleep 15; \
		elif [ "$$STATUS" = "POLL_ERROR" ] || [ -z "$$STATUS" ]; then \
			echo "  ...retrying status check for $(1)"; \
			sleep 15; \
		else \
			echo "CodeBuild for $(1) failed with status: $$STATUS"; \
			echo "View logs: aws codebuild batch-get-builds --ids $(_BUILD_ID) --region $(PRIMARY_REGION)"; \
			exit 1; \
		fi; \
	done
endef

ecr-login:
	@echo "ECR login is handled by CodeBuild — skipping"

build-catalog-primary: primary_infrastructure standby_infrastructure codebuild-infra
	$(call codebuild-build,catalog,catalog)

build-catalog-standby: build-catalog-primary
	@echo "catalog image already pushed to both regions by CodeBuild"

build-checkout-primary: primary_infrastructure standby_infrastructure codebuild-infra
	$(call codebuild-build,checkout,checkout)

build-checkout-standby: build-checkout-primary
	@echo "checkout image already pushed to both regions by CodeBuild"

build-ui-primary: primary_infrastructure standby_infrastructure codebuild-infra
	$(call codebuild-build,ui,ui)

build-ui-standby: build-ui-primary
	@echo "ui image already pushed to both regions by CodeBuild"

build-carts-primary: primary_infrastructure standby_infrastructure codebuild-infra
	$(call codebuild-build,carts,cart)

build-carts-standby: build-carts-primary
	@echo "carts image already pushed to both regions by CodeBuild"

build-assets-primary: primary_infrastructure standby_infrastructure codebuild-infra
	$(call codebuild-build,assets,assets)

build-assets-standby: build-assets-primary
	@echo "assets image already pushed to both regions by CodeBuild"

build-orders-primary: primary_infrastructure standby_infrastructure codebuild-infra
	$(call codebuild-build,orders,orders)

build-orders-standby: build-orders-primary
	@echo "orders image already pushed to both regions by CodeBuild"

####
# Infrastructure and ECS targets
####

primary_infrastructure: create-peer
	@echo "Deploy Infrastructure resources in ${PRIMARY_REGION}"
	@aws cloudformation deploy --template ./regionalBaseInfra.yaml --region ${PRIMARY_REGION} \
	--stack-name baseInfra${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV} KmsKey=retail-store-ar${ENV} PrimaryOnly=${PRIMARY_ONLY}

primary_ecs: build-catalog-primary build-checkout-primary build-ui-primary build-carts-primary build-assets-primary build-orders-primary primary_region_catalog-db orders-dsql-db carts-db
	@echo "Deploy ECS Services in ${PRIMARY_REGION}"
	@aws cloudformation deploy --template ./ecs.yaml --region ${PRIMARY_REGION} \
	--stack-name apps${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV} Tag=${TAG} KmsKey=retail-store-ar${ENV}

standby_infrastructure: create-peer
	@echo "Deploy Infrastructure resources in ${STANDBY_REGION}"
	@aws cloudformation deploy --template ./regionalBaseInfra.yaml --region ${STANDBY_REGION} \
	--stack-name baseInfra${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV} KmsKey=retail-store-ar${ENV}

standby_ecs: build-catalog-standby build-checkout-standby build-ui-standby build-carts-standby build-assets-standby build-orders-standby standby_region_catalog-db orders-dsql-db-standby
	@echo "Deploy ECS Services in ${STANDBY_REGION}"
	@aws cloudformation deploy --template ./ecs.yaml --region ${STANDBY_REGION} \
	--stack-name apps${ENV} --capabilities CAPABILITY_IAM --parameter-overrides Env=${ENV} Tag=${TAG} KmsKey=retail-store-ar${ENV}

global_routing: standby_ecs primary_ecs
	@echo "Deploy the Global Routing layer"
	@aws cloudformation deploy --region ${PRIMARY_REGION} --template ./globalRouting.yaml \
	--stack-name gr${ENV} --capabilities CAPABILITY_NAMED_IAM --parameter-overrides DomainName=demo${ENV}.io Env=${ENV} KmsKey=retail-store-ar${ENV}

region-switch: global_routing
	@echo "Deploy the ARC Region Switch Plan"
	$(eval PRIMARY_CLUSTER_ARN:=$(shell aws secretsmanager get-secret-value \
		--secret-id mr-app/ecs-cluster-arn-$(PRIMARY_REGION)$(ENV) \
		--region $(PRIMARY_REGION) --query "SecretString" --output text))
	$(eval STANDBY_CLUSTER_ARN:=$(shell aws secretsmanager get-secret-value \
		--secret-id mr-app/ecs-cluster-arn-$(STANDBY_REGION)$(ENV) \
		--region $(PRIMARY_REGION) --query "SecretString" --output text))
	@aws cloudformation deploy --region ${PRIMARY_REGION} --template ./failover.yaml \
	--stack-name region-switch${ENV} --capabilities CAPABILITY_NAMED_IAM \
	--parameter-overrides Env=${ENV} DomainName=demo${ENV}.io \
	PrimaryClusterArn=$(PRIMARY_CLUSTER_ARN) StandbyClusterArn=$(STANDBY_CLUSTER_ARN)
	@echo "Wiring plan health checks to Route53 records"
	$(eval PLAN_ARN:=$(shell aws cloudformation describe-stacks \
		--stack-name region-switch$(ENV) --region $(PRIMARY_REGION) \
		--query "Stacks[0].Outputs[?OutputKey=='RegionSwitchPlanArn'].OutputValue" --output text))
	$(eval PRIMARY_HC_ID:=$(shell aws arc-region-switch list-route53-health-checks \
		--arn $(PLAN_ARN) --region $(PRIMARY_REGION) --output json \
		| jq -r '.healthChecks[] | select(.region == "$(PRIMARY_REGION)") | .healthCheckId'))
	$(eval STANDBY_HC_ID:=$(shell aws arc-region-switch list-route53-health-checks \
		--arn $(PLAN_ARN) --region $(PRIMARY_REGION) --output json \
		| jq -r '.healthChecks[] | select(.region == "$(STANDBY_REGION)") | .healthCheckId'))
	@aws cloudformation deploy --region ${PRIMARY_REGION} --template ./globalRouting.yaml \
	--stack-name gr${ENV} --capabilities CAPABILITY_NAMED_IAM \
	--parameter-overrides DomainName=demo${ENV}.io Env=${ENV} KmsKey=retail-store-ar${ENV} \
	PrimaryHealthCheckId=$(PRIMARY_HC_ID) StandbyHealthCheckId=$(STANDBY_HC_ID)

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

orders-dsql-db: primary_infrastructure
	@echo "Creating Orders service DSQL cluster..."
	@aws cloudformation deploy --template ./database/dsql/orders-dsql-cluster.yml \
	--region ${PRIMARY_REGION} --stack-name orders-dsql-stack${ENV} --capabilities CAPABILITY_IAM \
	--parameter-overrides Env=${ENV} KmsKey=retail-store-ar${ENV}

orders-dsql-db-standby: orders-dsql-db
	@echo "Replicating DSQL endpoint parameter to ${STANDBY_REGION}..."
	$(eval _DSQL_ENDPOINT:=$(shell aws ssm get-parameter --name orders-dsql-cluster-Endpoint$(ENV) --region $(PRIMARY_REGION) --query "Parameter.Value" --output text))
	@aws ssm put-parameter --name orders-dsql-cluster-Endpoint$(ENV) --value "$(_DSQL_ENDPOINT)" \
	--type String --region ${STANDBY_REGION} --overwrite --no-cli-pager

carts-db: primary_infrastructure
	@echo "Verifying if the AWSServiceRoleForDynamoDBReplication exists; if not; this will be created for you..."
	$(eval resultDDB:=$(shell aws iam list-roles --query "length(Roles[?RoleName=='AWSServiceRoleForDynamoDBReplication'])"))
	@if [ "$(resultDDB)" -eq "0" ]; then \
    		aws iam create-service-linked-role --aws-service-name replication.dynamodb.amazonaws.com --no-cli-pager; \
    fi
	@echo "Creating Carts service DynamoDB Global Table in ${PRIMARY_REGION} and ${STANDBY_REGION}..."
	@aws cloudformation deploy --template ./database/dynamodb/global-table.yml \
	--region ${PRIMARY_REGION} --stack-name carts-db-stack${ENV} --capabilities CAPABILITY_IAM \
	--parameter-overrides Env=${ENV} NamingPrefix=carts KmsKey=retail-store-ar${ENV} WitnessRegion=us-east-2

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

restore-reconciliation: primary_infrastructure standby_infrastructure
	@echo "Creating IAM Role for restore-reconcliation"
	@aws cloudformation deploy --template ./database/crdr-reconciliation/src/crdr-roles.yaml --parameter-overrides KmsKey=retail-store-ar${ENV} Env=${ENV} --capabilities CAPABILITY_NAMED_IAM --stack-name crdr-roles${ENV}  --region ${PRIMARY_REGION}
	@echo "Creating SSM automation runbook in ${PRIMARY_REGION}"
	@aws cloudformation deploy --template ./database/crdr-reconciliation/src/cross-region-catalog-db-ssm.yaml --parameter-overrides Env=${ENV} --capabilities CAPABILITY_NAMED_IAM --stack-name crdr-catalog-ssm${ENV} --region ${PRIMARY_REGION}

	@echo "Creating reconciliation resources in ${STANDBY_REGION}"
	@echo "Step 1:Building Lambda Layers"
	./build-lambda-layer.sh
	@echo "Step 2:Deploying Lambda and SSM Runbook"
	$(eval result:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(STANDBY_REGION) --query "Parameter.Value" --output text ))
	@aws cloudformation package --template-file ./database/crdr-reconciliation/src/restore-reconcile-catalog-ssm.yaml --region ${STANDBY_REGION} --s3-bucket $(result) --output-template-file ./database/crdr-reconciliation/src/out.yaml
	@aws cloudformation deploy --template-file ./database/crdr-reconciliation/src/out.yaml --stack-name reconciliation-catalog-ssm${ENV} --region ${STANDBY_REGION} --capabilities CAPABILITY_NAMED_IAM --parameter-overrides Env=${ENV}

monitoring: restore-reconciliation
	@echo "Deploy the Monitoring Dashboard"
	@aws cloudformation deploy --region ${PRIMARY_REGION} --template ./monitoring.yml \
	--stack-name monitoring${ENV} --capabilities CAPABILITY_NAMED_IAM --parameter-overrides PrimaryRegion=${PRIMARY_REGION} Env=${ENV} SecondaryRegion=${STANDBY_REGION}

secrets-rotation: primary_region_catalog-db
	@echo "Creating secrets rotation resources in ${PRIMARY_REGION}"
	@echo "Step 1:Building Lambda Layers"
	./database/secrets-rotation/build-lambda-layer.sh
	@echo "Step 2:Deploying Lambda"
	$(eval result:=$(shell aws ssm get-parameter --name canaryBucketName$(ENV) --region $(PRIMARY_REGION) --query "Parameter.Value" --output text ))
	@aws cloudformation package --template-file ./database/secrets-rotation/src/secrets-rotation.yaml --region ${PRIMARY_REGION} --s3-bucket $(result) --output-template-file ./database/secrets-rotation/src/out.yaml
	@aws cloudformation deploy --template-file ./database/secrets-rotation/src/out.yaml --stack-name secrets-rotation${ENV} --region ${PRIMARY_REGION} --capabilities CAPABILITY_NAMED_IAM --parameter-overrides Env=${ENV} CatalogDBCredentialsSecretId=mr-app/catalog-global-db-cluster-UserCredentials${ENV}

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

####
# Destroy targets
####

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
	@aws cloudformation delete-stack --stack-name crdr-catalog-ssm${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation delete-stack --stack-name reconciliation-catalog-ssm${ENV} --region ${STANDBY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name reconciliation-catalog-ssm${ENV} --region ${STANDBY_REGION}
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

destroy-global_routing: destroy-canaries-standby destroy-canaries-primary destroy-region-switch destroy-restore-reconciliation-ssm
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

destroy-codebuild:
	@echo "Deleting CodeBuild stack..."
	@aws cloudformation delete-stack --stack-name codebuild${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name codebuild${ENV} --region ${PRIMARY_REGION}

destroy-infra: destroy-ecr-standby destroy-ecr-primary destroy-databases-standby destroy-databases-primary destroy-client-primary destroy-client-standby destroy-codebuild
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

destroy-region-switch:
	@echo "Deleting region switch plan..."
	@aws cloudformation delete-stack --stack-name region-switch${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name region-switch${ENV} --region ${PRIMARY_REGION}

destroy-databases-primary: destroy-secrets-rotation destroy-apps-primary destroy-databases-standby
	@echo "Deleting databases in ${PRIMARY_REGION}..."
	@aws cloudformation delete-stack --stack-name catalog-db-stack${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation delete-stack --stack-name orders-dsql-stack${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation delete-stack --stack-name carts-db-stack${ENV} --region ${PRIMARY_REGION}

	@aws cloudformation wait stack-delete-complete --stack-name catalog-db-stack${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name orders-dsql-stack${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name carts-db-stack${ENV} --region ${PRIMARY_REGION}

destroy-databases-standby: destroy-apps-standby
	@echo "Deleting databases in ${STANDBY_REGION}..."
	@aws cloudformation delete-stack --stack-name catalog-db-stack${ENV} --region ${STANDBY_REGION}
	@aws ssm delete-parameter --name orders-dsql-cluster-Endpoint$(ENV) --region ${STANDBY_REGION} --no-cli-pager 2>/dev/null || true

	@aws cloudformation wait stack-delete-complete --stack-name catalog-db-stack${ENV} --region ${STANDBY_REGION}

destroy-client-primary:
	@echo "Deleting client in ${PRIMARY_REGION}"
	@aws cloudformation delete-stack --stack-name client${ENV} --region ${PRIMARY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name client${ENV} --region ${PRIMARY_REGION}

destroy-client-standby:
	@echo "Deleting client in ${STANDBY_REGION}"
	@aws cloudformation delete-stack --stack-name client${ENV} --region ${STANDBY_REGION}
	@aws cloudformation wait stack-delete-complete --stack-name client${ENV} --region ${STANDBY_REGION}
