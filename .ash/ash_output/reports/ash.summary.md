# ASH Security Scan Report

- **Report generated**: 2026-02-23T22:52:08+00:00
- **Time since scan**: 2 minutes

## Scan Metadata

- **Project**: ASH
- **Scan executed**: 2026-02-23T22:49:10+00:00
- **ASH version**: 3.2.1

## Summary

### Scanner Results

The table below shows findings by scanner, with status based on severity thresholds and dependencies:

- **Severity levels**:
  - **Suppressed (S)**: Findings that have been explicitly suppressed and don't affect scanner status
  - **Critical (C)**: Highest severity findings that require immediate attention
  - **High (H)**: Serious findings that should be addressed soon
  - **Medium (M)**: Moderate risk findings
  - **Low (L)**: Lower risk findings
  - **Info (I)**: Informational findings with minimal risk
- **Duration (Time)**: Time taken by the scanner to complete its execution
- **Actionable**: Number of findings at or above the threshold severity level that require attention
- **Result**:
  - **PASSED** = No findings at or above threshold
  - **FAILED** = Findings at or above threshold
  - **MISSING** = Required dependencies not available
  - **SKIPPED** = Scanner explicitly disabled
  - **ERROR** = Scanner execution error
- **Threshold**: The minimum severity level that will cause a scanner to fail
  - Thresholds: ALL, LOW, MEDIUM, HIGH, CRITICAL
  - Source: Values in parentheses indicate where the threshold is set:
    - `global` (global_settings section in the ASH_CONFIG used)
    - `config` (scanner config section in the ASH_CONFIG used)
    - `scanner` (default configuration in the plugin, if explicitly set)
- **Statistics calculation**:
  - All statistics are calculated from the final aggregated SARIF report
  - Suppressed findings are counted separately and do not contribute to actionable findings
  - Scanner status is determined by comparing actionable findings to the threshold

| Scanner | Suppressed | Critical | High | Medium | Low | Info | Actionable | Result | Threshold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| bandit | 0 | 4 | 0 | 0 | 74 | 0 | 4 | FAILED | MEDIUM (global) |
| cdk-nag | 0 | 60 | 0 | 0 | 0 | 84 | 60 | SKIPPED | MEDIUM (global) |
| cfn-nag | 0 | 0 | 0 | 0 | 0 | 0 | 0 | MISSING | MEDIUM (global) |
| checkov | 0 | 45 | 0 | 0 | 0 | 0 | 45 | SKIPPED | MEDIUM (global) |
| detect-secrets | 0 | 5774 | 0 | 0 | 0 | 0 | 5774 | SKIPPED | MEDIUM (global) |
| grype | 0 | 0 | 0 | 0 | 0 | 0 | 0 | MISSING | MEDIUM (global) |
| npm-audit | 0 | 0 | 0 | 0 | 0 | 0 | 0 | PASSED | MEDIUM (global) |
| opengrep | 0 | 0 | 0 | 0 | 0 | 0 | 0 | MISSING | MEDIUM (global) |
| semgrep | 2 | 24 | 0 | 0 | 0 | 0 | 24 | FAILED | MEDIUM (global) |
| syft | 0 | 0 | 0 | 0 | 0 | 0 | 0 | MISSING | MEDIUM (global) |

### Top 10 Hotspots

Files with the highest number of security findings:

| Finding Count | File Location |
| ---: | --- |
| 885 | source/checkout/node_modules/.package-lock.json |
| 869 | source/checkout/node_modules/@typescript-eslint/eslint-plugin/dist/tsconfig.build.tsbuildinfo |
| 601 | source/checkout/node_modules/@typescript-eslint/scope-manager/dist/tsconfig.build.tsbuildinfo |
| 429 | source/checkout/node_modules/@typescript-eslint/type-utils/dist/tsconfig.build.tsbuildinfo |
| 424 | source/checkout/node_modules/@typescript-eslint/utils/dist/tsconfig.build.tsbuildinfo |
| 412 | source/checkout/node_modules/@typescript-eslint/typescript-estree/dist/tsconfig.build.tsbuildinfo |
| 349 | source/checkout/node_modules/@typescript-eslint/parser/dist/tsconfig.build.tsbuildinfo |
| 278 | source/checkout/node_modules/@typescript-eslint/project-service/dist/tsconfig.build.tsbuildinfo |
| 273 | source/checkout/node_modules/@typescript-eslint/visitor-keys/dist/tsconfig.build.tsbuildinfo |
| 271 | source/checkout/node_modules/@typescript-eslint/types/dist/tsconfig.build.tsbuildinfo |

<h2>Detailed Findings</h2>

<details>
<summary>Show 20 of 5907 actionable findings</summary>

### Finding 1: B303

- **Severity**: HIGH
- **Scanner**: bandit
- **Rule ID**: B303
- **Location**: deployment/database/crdr-reconciliation/src/function/package/python/pymysql/_auth.py:151-153

**Description**:
Use of insecure MD2, MD4, MD5, or SHA1 hash function.

**Code Snippet**:
```
padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA1()),
            algorithm=hashes.SHA1(),
```

---

### Finding 2: B303

- **Severity**: HIGH
- **Scanner**: bandit
- **Rule ID**: B303
- **Location**: deployment/database/crdr-reconciliation/src/function/package/python/pymysql/_auth.py:152-154

**Description**:
Use of insecure MD2, MD4, MD5, or SHA1 hash function.

**Code Snippet**:
```
mgf=padding.MGF1(algorithm=hashes.SHA1()),
            algorithm=hashes.SHA1(),
            label=None,
```

---

### Finding 3: B303

- **Severity**: HIGH
- **Scanner**: bandit
- **Rule ID**: B303
- **Location**: deployment/database/secrets-rotation/src/function/package/python/pymysql/_auth.py:151-153

**Description**:
Use of insecure MD2, MD4, MD5, or SHA1 hash function.

**Code Snippet**:
```
padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA1()),
            algorithm=hashes.SHA1(),
```

---

### Finding 4: B303

- **Severity**: HIGH
- **Scanner**: bandit
- **Rule ID**: B303
- **Location**: deployment/database/secrets-rotation/src/function/package/python/pymysql/_auth.py:152-154

**Description**:
Use of insecure MD2, MD4, MD5, or SHA1 hash function.

**Code Snippet**:
```
mgf=padding.MGF1(algorithm=hashes.SHA1()),
            algorithm=hashes.SHA1(),
            label=None,
```

---

### Finding 5: CKV_AWS_51

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_51
- **Location**: deployment/regionalBaseInfra.yaml:266-275

**Description**:
Ensure ECR Image Tags are immutable

**Code Snippet**:
```
CheckoutRepo:
    Type: AWS::ECR::Repository
    Properties:
      ImageScanningConfiguration:
        ScanOnPush: true
      RepositoryName: !Sub 'checkout${Env}'
      ImageTagMutability: MUTABLE
      EncryptionConfiguration:
        EncryptionType: KMS
        KmsKey: !Ref KmsKey
```

---

### Finding 6: CKV_AWS_51

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_51
- **Location**: deployment/regionalBaseInfra.yaml:276-285

**Description**:
Ensure ECR Image Tags are immutable

**Code Snippet**:
```
CatalogRepo:
    Type: AWS::ECR::Repository
    Properties:
      ImageScanningConfiguration:
          ScanOnPush: true
      RepositoryName: !Sub 'catalog${Env}'
      ImageTagMutability: MUTABLE
      EncryptionConfiguration:
        EncryptionType: KMS
        KmsKey: !Ref KmsKey
```

---

### Finding 7: CKV_AWS_51

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_51
- **Location**: deployment/regionalBaseInfra.yaml:286-295

**Description**:
Ensure ECR Image Tags are immutable

**Code Snippet**:
```
CartsRepo:
    Type: AWS::ECR::Repository
    Properties:
      ImageScanningConfiguration:
        ScanOnPush: true
      RepositoryName: !Sub 'carts${Env}'
      ImageTagMutability: MUTABLE
      EncryptionConfiguration:
        EncryptionType: KMS
        KmsKey: !Ref KmsKey
```

---

### Finding 8: CKV_AWS_51

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_51
- **Location**: deployment/regionalBaseInfra.yaml:296-305

**Description**:
Ensure ECR Image Tags are immutable

**Code Snippet**:
```
AssetsRepo:
    Type: AWS::ECR::Repository
    Properties:
      ImageScanningConfiguration:
        ScanOnPush: true
      RepositoryName: !Sub 'assets${Env}'
      ImageTagMutability: MUTABLE
      EncryptionConfiguration:
        EncryptionType: KMS
        KmsKey: !Ref KmsKey
```

---

### Finding 9: CKV_AWS_51

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_51
- **Location**: deployment/regionalBaseInfra.yaml:306-315

**Description**:
Ensure ECR Image Tags are immutable

**Code Snippet**:
```
OrdersRepo:
    Type: AWS::ECR::Repository
    Properties:
      ImageScanningConfiguration:
        ScanOnPush: true
      RepositoryName: !Sub 'orders${Env}'
      ImageTagMutability: MUTABLE
      EncryptionConfiguration:
        EncryptionType: KMS
        KmsKey: !Ref KmsKey
```

---

### Finding 10: CKV_AWS_51

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_51
- **Location**: deployment/regionalBaseInfra.yaml:316-325

**Description**:
Ensure ECR Image Tags are immutable

**Code Snippet**:
```
UIRepo:
    Type: AWS::ECR::Repository
    Properties:
      ImageScanningConfiguration:
        ScanOnPush: true
      RepositoryName: !Sub 'ui${Env}'
      ImageTagMutability: MUTABLE
      EncryptionConfiguration:
        EncryptionType: KMS
        KmsKey: !Ref KmsKey
```

---

### Finding 11: CKV_AWS_23

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_23
- **Location**: deployment/ecs.yaml:136-143

**Description**:
Ensure every security groups rule has a description

**Code Snippet**:
```
VPCEndpointSecurityGroupIngress:
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: !Sub '{{resolve:ssm:VPCEndpointSecretsManagerSGId${Env}}}'
      IpProtocol: tcp
      FromPort: 443
      ToPort: 443
      SourceSecurityGroupId: !Ref sgTask
```

---

### Finding 12: CKV_AWS_23

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_23
- **Location**: deployment/ecs.yaml:144-151

**Description**:
Ensure every security groups rule has a description

**Code Snippet**:
```
VPCEndpointSSMSecurityGroupIngress:
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: !Sub '{{resolve:ssm:VPCEndpointSSMSGId${Env}}}'
      IpProtocol: tcp
      FromPort: 443
      ToPort: 443
      SourceSecurityGroupId: !Ref sgTask
```

---

### Finding 13: CKV_AWS_91

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_91
- **Location**: deployment/ecs.yaml:306-319

**Description**:
Ensure the ELBv2 (Application/Network) has access logging enabled

**Code Snippet**:
```
Alb:
    Type: AWS::ElasticLoadBalancingV2::LoadBalancer
    Properties:
      Scheme: internal
      LoadBalancerAttributes:
        - Key: routing.http.drop_invalid_header_fields.enabled
          Value: true
      SecurityGroups: 
        - !Ref sgAlb
      Subnets:
        - !Sub '{{resolve:ssm:Subnet1${Env}}}'
        - !Sub '{{resolve:ssm:Subnet2${Env}}}'
        - !Sub '{{resolve:ssm:Subnet3${Env}}}'
      Type: application
```

---

### Finding 14: CKV_AWS_103

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_103
- **Location**: deployment/ecs.yaml:341-349

**Description**:
Ensure that Load Balancer Listener is using at least TLS v1.2

**Code Snippet**:
```
AlbListener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties: 
      DefaultActions: 
        - Type: forward
          TargetGroupArn: !Ref AlbTargetGroup
      LoadBalancerArn: !Ref Alb
      Port: 80
      Protocol: HTTP
```

---

### Finding 15: CKV_AWS_2

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_2
- **Location**: deployment/ecs.yaml:341-349

**Description**:
Ensure ALB protocol is HTTPS

**Code Snippet**:
```
AlbListener:
    Type: AWS::ElasticLoadBalancingV2::Listener
    Properties: 
      DefaultActions: 
        - Type: forward
          TargetGroupArn: !Ref AlbTargetGroup
      LoadBalancerArn: !Ref Alb
      Port: 80
      Protocol: HTTP
```

---

### Finding 16: CKV_AWS_18

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_18
- **Location**: deployment/regionalVpc.yaml:164-176

**Description**:
Ensure the S3 bucket has access logging enabled

**Code Snippet**:
```
canaryBucket:
    Type: AWS::S3::Bucket
    Properties:
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      LifecycleConfiguration:
        Rules:
          - Id: DeleteAfter24Hours
            Status: Enabled
            ExpirationInDays: 1
```

---

### Finding 17: CKV_AWS_21

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_21
- **Location**: deployment/regionalVpc.yaml:164-176

**Description**:
Ensure the S3 bucket has versioning enabled

**Code Snippet**:
```
canaryBucket:
    Type: AWS::S3::Bucket
    Properties:
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      LifecycleConfiguration:
        Rules:
          - Id: DeleteAfter24Hours
            Status: Enabled
            ExpirationInDays: 1
```

---

### Finding 18: CKV_AWS_23

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_23
- **Location**: deployment/windows.yaml:76-94

**Description**:
Ensure every security groups rule has a description

**Code Snippet**:
```
SecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      VpcId: !Ref 'VpcId'
      GroupDescription: OutboundOnly
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 3389
          ToPort: 3389
          CidrIp: 10.1.0.0/16
      SecurityGroupEgress:
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIp: 0.0.0.0/0
        - IpProtocol: tcp
          FromPort: 80
          ToPort: 80
          CidrIp: 0.0.0.0/0
```

---

### Finding 19: CKV_AWS_23

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_23
- **Location**: deployment/windows.yaml:95-102

**Description**:
Ensure every security groups rule has a description

**Code Snippet**:
```
VPCEndpointSSMSecurityGroupIngress:
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: !Sub '{{resolve:ssm:VPCEndpointSSMSGId${Env}}}'
      IpProtocol: tcp
      FromPort: 443
      ToPort: 443
      SourceSecurityGroupId: !Ref SecurityGroup
```

---

### Finding 20: CKV_AWS_23

- **Severity**: HIGH
- **Scanner**: checkov
- **Rule ID**: CKV_AWS_23
- **Location**: deployment/windows.yaml:103-110

**Description**:
Ensure every security groups rule has a description

**Code Snippet**:
```
VPCEndpointSecretsManagerSecurityGroupIngress:
    Type: AWS::EC2::SecurityGroupIngress
    Properties:
      GroupId: !Sub '{{resolve:ssm:VPCEndpointSecretsManagerSGId${Env}}}'
      IpProtocol: tcp
      FromPort: 443
      ToPort: 443
      SourceSecurityGroupId: !Ref SecurityGroup
```


> Note: Showing 20 of 5907 total actionable findings. Configure `max_detailed_findings` to adjust this limit.

</details>

---

*Report generated by [Automated Security Helper (ASH)](https://github.com/awslabs/automated-security-helper) at 2026-02-23T22:52:08+00:00*