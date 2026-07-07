#!/bin/bash

# Initialize variables
ENV=""
SERVICES=()
# Default region falls back to the configured AWS_REGION/AWS_DEFAULT_REGION, then us-east-1
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --env)
            ENV="$2"
            shift 2
            ;;
        --region)
            REGION="$2"
            shift 2
            ;;
        --services)
            IFS=',' read -r -a SERVICES <<< "$2"
            shift 2
            ;;
        *)
            echo "Unknown parameter passed: $1"
            echo "Usage: $0 [--env <Env>] [--region <Region>] --services <Service1,Service2,...>"
            exit 1
            ;;
    esac
done

# Ensure at least one service is provided
if [ "${#SERVICES[@]}" -lt 1 ]; then
  echo "Usage: $0 [--env <Env>] --services <Service1,Service2,...>"
  exit 1
fi

# Function to get the cluster ARN with the specified tag using Resource Groups Tagging API
get_cluster_arn() {
  local tag_value
  if [ -z "$ENV" ]; then
    tag_value="mr-app-ecs-cluster"
  else
    tag_value="mr-app-ecs-cluster${ENV}"
  fi
  # The Name tag can match several cluster ARNs: deleted clusters linger as
  # INACTIVE tombstones (with their tags) after each stack create/delete cycle.
  # Collect all matches, then keep only the ACTIVE one.
  local matched_arns
  matched_arns=$(aws resourcegroupstaggingapi get-resources \
    --region "$REGION" \
    --tag-filters Key=Name,Values=$tag_value \
    --resource-type-filters ecs:cluster \
    --query 'ResourceTagMappingList[].ResourceARN' \
    --output text)

  if [ -z "$matched_arns" ]; then
    echo ""
    return
  fi

  local cluster_arn
  cluster_arn=$(aws ecs describe-clusters \
    --region "$REGION" \
    --clusters $matched_arns \
    --query "clusters[?status=='ACTIVE'].clusterArn | [0]" \
    --output text)

  # Normalize AWS CLI's "None" (no ACTIVE match) to empty string
  if [ "$cluster_arn" = "None" ]; then
    cluster_arn=""
  fi
  echo "$cluster_arn"
}

# Function to force a new deployment for a given service
force_new_deployment() {
  local cluster_arn=$1
  local service_name=$2

  aws ecs update-service \
    --region "$REGION" \
    --cluster "$cluster_arn" \
    --service "$service_name" \
    --force-new-deployment \
    --no-cli-pager

  echo "New deployment forced for service '$service_name' in cluster $cluster_arn."
}

# Get the cluster ARN
CLUSTER_ARN=$(get_cluster_arn)

# Check if the cluster ARN was found
if [ -z "$CLUSTER_ARN" ]; then
  if [ -z "$ENV" ]; then
    echo "Cluster with tag 'Name=mr-app-ecs-cluster' not found."
  else
    echo "Cluster with tag 'Name=mr-app-ecs-cluster${ENV}' not found."
  fi
  exit 1
fi

# Force a new deployment for each service in the list.
# ECS service names carry the ${ENV} suffix (e.g. catalog-test), so append it.
for service in "${SERVICES[@]}"; do
  force_new_deployment "$CLUSTER_ARN" "${service}${ENV}"
done
