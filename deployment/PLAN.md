# Plan: Eliminate Internet Gateway from VPC

## Summary

Remove the IGW, NAT gateway, and all public subnets. Replace all outbound internet
dependency with VPC endpoints. Mirror public ECR sidecar images into private ECR repos
via CodeBuild.

---

## 1. Add VPC Endpoints to `regionalBaseInfra.yaml`

Add **12 new endpoints** following the existing pattern (endpoint + security group + SSM param):

### Interface Endpoints (10)

| Service | ServiceName | SG Name | SSM Param |
|---|---|---|---|
| ECR API | `ecr.api` | `VPCEndpointECRApiSecurityGroup` | `VPCEndpointECRApiSGId${Env}` |
| ECR Docker | `ecr.dkr` | `VPCEndpointECRDkrSecurityGroup` | `VPCEndpointECRDkrSGId${Env}` |
| CloudWatch Logs | `logs` | `VPCEndpointLogsSecurityGroup` | `VPCEndpointLogsSGId${Env}` |
| STS | `sts` | `VPCEndpointSTSSecurityGroup` | `VPCEndpointSTSSGId${Env}` |
| KMS | `kms` | `VPCEndpointKMSSecurityGroup` | `VPCEndpointKMSSGId${Env}` |
| CloudWatch Monitoring | `monitoring` | `VPCEndpointMonitoringSecurityGroup` | `VPCEndpointMonitoringSGId${Env}` |
| X-Ray | `xray` | `VPCEndpointXRaySecurityGroup` | `VPCEndpointXRaySGId${Env}` |
| ECS | `ecs` | `VPCEndpointECSSecurityGroup` | `VPCEndpointECSSGId${Env}` |
| ECS Telemetry | `ecs-telemetry` | (share ECS SG) | — |
| DSQL Management | `dsql` | `VPCEndpointDSQLSecurityGroup` | `VPCEndpointDSQLSGId${Env}` |

All interface endpoints: `PrivateDnsEnabled: true`, placed in all 3 private subnets.

### Gateway Endpoints (1)

| Service | ServiceName |
|---|---|
| DynamoDB | `dynamodb` |

Same pattern as existing S3 gateway — `RouteTableIds: [PrivateRouteTable]`, no SG.

### DSQL Connection Endpoint (1, cluster-specific)

Added to `database/dsql/orders-dsql-cluster.yml` because the service name is
cluster-specific (`com.amazonaws.${Region}.dsql-XXXX`), obtained via
`GetVpcEndpointServiceName` API with the cluster ID. Requires a Custom Resource (Lambda)
or a post-deploy Makefile step using `aws dsql get-vpc-endpoint-service-name` then
`aws ec2 create-vpc-endpoint`.

With `PrivateDnsEnabled: true` on the connection endpoint, the existing `DSQL_ENDPOINT`
SSM parameter value resolves to private IPs — no application code changes needed.

---

## 2. Mirror Public ECR Images via CodeBuild

Three sidecar images use `public.ecr.aws` (no VPC endpoint exists for public ECR):

| Public Image | Private Repo Name |
|---|---|
| `public.ecr.aws/cloudwatch-agent/cloudwatch-agent:latest` | `cloudwatch-agent${Env}` |
| `public.ecr.aws/aws-observability/adot-autoinstrumentation-java:v1.32.5` | `adot-autoinstrumentation-java${Env}` |
| `public.ecr.aws/aws-observability/adot-autoinstrumentation-node:v0.3.0` | `adot-autoinstrumentation-node${Env}` |

### 2a. Add 3 new ECR repos to `regionalBaseInfra.yaml`

Follow existing pattern (lines 266-325): `ImageScanningConfiguration`, `EncryptionConfiguration: KMS`.

### 2b. Add `mirror-sidecar-images` Makefile target using CodeBuild

The existing CodeBuild project has internet access, Docker, and ECR auth. Add a Makefile
target that invokes it with `--buildspec-override` containing an inline buildspec:

```yaml
version: 0.2
phases:
  pre_build:
    commands:
      - aws ecr get-login-password --region $PRIMARY_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$PRIMARY_REGION.amazonaws.com
      - |
        if [ "$PRIMARY_ONLY" != "true" ]; then
          aws ecr get-login-password --region $STANDBY_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$STANDBY_REGION.amazonaws.com
        fi
  build:
    commands:
      - |
        for ENTRY in \
          "cloudwatch-agent:public.ecr.aws/cloudwatch-agent/cloudwatch-agent:latest" \
          "adot-autoinstrumentation-java:public.ecr.aws/aws-observability/adot-autoinstrumentation-java:v1.32.5" \
          "adot-autoinstrumentation-node:public.ecr.aws/aws-observability/adot-autoinstrumentation-node:v0.3.0"; do
          REPO=${ENTRY%%:*}; SRC=${ENTRY#*:}; TAG_VAL=${SRC##*:}
          docker pull $SRC
          docker tag $SRC $AWS_ACCOUNT_ID.dkr.ecr.$PRIMARY_REGION.amazonaws.com/${REPO}${ENV_SUFFIX}:$TAG_VAL
          docker push $AWS_ACCOUNT_ID.dkr.ecr.$PRIMARY_REGION.amazonaws.com/${REPO}${ENV_SUFFIX}:$TAG_VAL
          if [ "$PRIMARY_ONLY" != "true" ]; then
            docker tag $SRC $AWS_ACCOUNT_ID.dkr.ecr.$STANDBY_REGION.amazonaws.com/${REPO}${ENV_SUFFIX}:$TAG_VAL
            docker push $AWS_ACCOUNT_ID.dkr.ecr.$STANDBY_REGION.amazonaws.com/${REPO}${ENV_SUFFIX}:$TAG_VAL
          fi
        done
```

This target should be a prerequisite of `primary_ecs`/`standby_ecs` alongside `build-images`.

### 2c. Update `ecs.yaml` image references (8 locations)

Replace all `public.ecr.aws/...` with private ECR equivalents:
- Lines 468, 596, 993, 1142: CW Agent -> `${AccountId}.dkr.ecr.${Region}.amazonaws.com/cloudwatch-agent${Env}:latest`
- Lines 482, 610, 1156: ADOT Java -> `${AccountId}.dkr.ecr.${Region}.amazonaws.com/adot-autoinstrumentation-java${Env}:v1.32.5`
- Line 1007: ADOT Node -> `${AccountId}.dkr.ecr.${Region}.amazonaws.com/adot-autoinstrumentation-node${Env}:v0.3.0`

### 2d. Update `codebuild.yaml` IAM policy

Add the 3 new repo ARNs (both regions) to `CodeBuildServiceRole` ECR permissions (lines 49-61).

---

## 3. Add Security Group Ingress Rules for New Endpoints

### `ecs.yaml` — ingress from `sgTask` to:

- `VPCEndpointECRApiSGId${Env}`
- `VPCEndpointECRDkrSGId${Env}`
- `VPCEndpointLogsSGId${Env}`
- `VPCEndpointSTSSGId${Env}`
- `VPCEndpointKMSSGId${Env}`
- `VPCEndpointMonitoringSGId${Env}`
- `VPCEndpointXRaySGId${Env}`
- `VPCEndpointECSSGId${Env}`
- `VPCEndpointDSQLSGId${Env}`

### `canaries.yaml` — ingress from `canarySg` to:

- `VPCEndpointLogsSGId${Env}`
- `VPCEndpointMonitoringSGId${Env}`
- `VPCEndpointXRaySGId${Env}`
- `VPCEndpointSTSSGId${Env}`

### `database/aurora/aurora-global-primary-cluster.yml` — ingress from `LambdaSecurityGroup` to:

- `VPCEndpointLogsSGId${Env}`

### `database/secrets-rotation/src/secrets-rotation.yaml`:

- Add **egress rule** on Lambda SG to `VPCEndpointLogsSGId${Env}` (443) — this Lambda has
  restrictive egress (only MySQL 3306 + SM 443), needs explicit egress for Logs endpoint
- Add **ingress rule** on `VPCEndpointLogsSGId${Env}` from Lambda SG

### `database/crdr-reconciliation/src/restore-reconcile-catalog-ssm.yaml` — ingress from `LambdaSecurityGroup` to:

- `VPCEndpointLogsSGId${Env}`

---

## 4. Remove Internet-Facing Infrastructure

### `regionalBaseInfra.yaml` — delete:

- `Igw`, `IgwAttach` (lines 74-80)
- `prvRouteZero` — `0.0.0.0/0 -> NAT` route (lines 82-88)
- `natEip1`, `natGW1` (lines 96-102)
- `pubRouteTable`, `pubRoute` (lines 103-118)
- `pubSnRta1`, `pubSnRta2`, `pubSnRta3` (lines 119, 130, 141)
- `publicSubnet1`, `publicSubnet2`, `publicSubnet3` (lines 124, 135, 146)
- `PubSubnet1Param`, `PubSubnet2Param`, `PubSubnet3Param` (lines 358-375)
- `PublicCidrBlock1/2/3` from Mappings (lines 29-31, 40-42)

### `regionalVpc.yaml` — delete:

- `PublicCidrBlock1/2/3` from Mappings (lines 29-31, 40-42)

### Preserve:

- `prvRoutePeer` (VPC peering route, line 89)
- `PrivateRouteTable` (line 260)

---

## 5. DSQL Connection Endpoint

DSQL PrivateLink requires two endpoint types
([docs](https://docs.aws.amazon.com/aurora-dsql/latest/userguide/privatelink-managing-clusters.html)):

1. **Management endpoint** (`com.amazonaws.${Region}.dsql`) — static, goes in
   `regionalBaseInfra.yaml`.

2. **Connection endpoint** (`com.amazonaws.${Region}.dsql-XXXX`) — cluster-specific.
   Added to `database/dsql/orders-dsql-cluster.yml` via Custom Resource or Makefile step:
   - Call `aws dsql get-vpc-endpoint-service-name --identifier <cluster-id>`
   - Create VPC endpoint with returned service name, `PrivateDnsEnabled: true`

---

## 6. Files Modified

| File | Changes |
|---|---|
| `regionalBaseInfra.yaml` | +12 VPC endpoints, +3 ECR repos, -IGW, -NAT, -public subnets, -public mappings |
| `regionalVpc.yaml` | -PublicCidrBlock mappings |
| `ecs.yaml` | Replace 8 public ECR image refs, +9 SG ingress rules |
| `canaries.yaml` | +4 SG ingress rules |
| `database/dsql/orders-dsql-cluster.yml` | +DSQL connection VPC endpoint |
| `database/aurora/aurora-global-primary-cluster.yml` | +1 SG ingress rule |
| `database/secrets-rotation/src/secrets-rotation.yaml` | +1 SG egress + 1 SG ingress rule |
| `database/crdr-reconciliation/src/restore-reconcile-catalog-ssm.yaml` | +1 SG ingress rule |
| `codebuild.yaml` | +3 ECR repo ARNs in IAM policy |
| `Makefile` | +`mirror-sidecar-images` target, update deps, update destroy targets |
| `tests/test_makefile_dependencies.py` | Update for new targets |
