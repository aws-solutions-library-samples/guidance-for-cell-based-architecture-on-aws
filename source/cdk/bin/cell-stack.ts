import * as cdk from 'aws-cdk-lib';
import {
    aws_dynamodb as dynamodb,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecsPatterns,
    aws_iam as iam,
    aws_kinesis as kinesis,
    Stack,
    StackProps
} from 'aws-cdk-lib';
import {Construct} from 'constructs';
import * as synthetics from 'aws-cdk-lib/aws-synthetics';
import * as fs from 'fs';
import {AclCidr, AclTraffic, Action, TrafficDirection} from "aws-cdk-lib/aws-ec2";

export class CellStack extends Stack {
    constructor(scope: Construct, id: string, props?: StackProps) {
        super(scope, id, props);

        const cell_id = new cdk.CfnParameter(this, "cell_id", {
            type: "String",
            description: "The unique ID of this cell. (Will be appended to all resources)",
            // Necessary, e.g., for synthetics name.
            allowedPattern: '[a-z\\-0-9]*',
            constraintDescription: 'A name consists of lowercase letters, numbers, ' +
                'hyphens or underscores with no spaces.'
        });

        const image_uri = new cdk.CfnParameter(this, "image_uri", {
            type: "String",
            description: "URI of the repository",
        });

        const datalakeStream = kinesis.Stream.fromStreamArn(this, 'dataLakeStream',
            cdk.Fn.importValue('cellDataLakeArn').toString())
        const ddb_table = new dynamodb.Table(this, 'Cell-Table', {
            tableName: 'Cell-' + cell_id.valueAsString,
            partitionKey: {name: 'username', type: dynamodb.AttributeType.STRING},
            sortKey: {name: 'key', type: dynamodb.AttributeType.STRING},
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            removalPolicy: cdk.RemovalPolicy.DESTROY,
            kinesisStream: datalakeStream,
        })

        new cdk.CfnOutput(this, 'ddbTableName', {
            value: ddb_table.tableName,
            //exportName: 'ddbTableName'
        });

        const vpc = new ec2.Vpc(this, 'Cell-VPC', {
            vpcName: "Cell-VPC-" + cell_id.valueAsString,
            ipAddresses: ec2.IpAddresses.cidr("10.0.0.0/16"),
            natGateways: 1 // For testing only
        })
        // Uncomment this to simulate a bad deployment.
        // this.create_denyNacls(vpc)

        const service = this.ecs_service(vpc, cell_id, image_uri, ddb_table);

        this.create_canary(cell_id, service)
    }

    create_denyNacls(vpc: ec2.Vpc) {
        const nacl = new ec2.NetworkAcl(this, 'DenyAllNacl', {
            vpc: vpc,
            networkAclName: 'denyAllNacl',
            subnetSelection: {
                subnetType: ec2.SubnetType.PUBLIC,
                onePerAz: false,
            }
        })
        nacl.addEntry('BlockAllOutgoing', {
            cidr: AclCidr.anyIpv4(),
            ruleNumber: 99,
            traffic: AclTraffic.allTraffic(),
            direction: TrafficDirection.EGRESS,
            ruleAction: Action.DENY
        })
    }

    create_canary(cell_id: cdk.CfnParameter, service: ecsPatterns.ApplicationLoadBalancedFargateService) {
        const file = fs.readFileSync('./canary/canary-script-2.py')

        const canary = new synthetics.Canary(this, 'Inline Canary', {
            canaryName: 'cell-canary-' + cell_id.valueAsString,
            test: synthetics.Test.custom({
                code: synthetics.Code.fromInline(file.toString()),
                handler: 'index.handler',
            }),
            environmentVariables: {
                dnsName: service.loadBalancer.loadBalancerDnsName,
                cellid: cell_id.valueAsString,
            },
            schedule: synthetics.Schedule.rate(cdk.Duration.minutes(1)),
            startAfterCreation: true,
            runtime: new synthetics.Runtime('syn-python-selenium-1.3', synthetics.RuntimeFamily.PYTHON),
            timeToLive: cdk.Duration.hours(1),
        });

        canary.role.attachInlinePolicy(new iam.Policy(this, 'userpool-policy', {
            statements: [new iam.PolicyStatement({
                actions: ['lambda:InvokeFunction'],
                // TODO restrict this to canary-creat-token
                resources: ['*'],
            })],
        }))
    }

    ecs_service(vpc: ec2.Vpc, cell_id: cdk.CfnParameter, image_uri: cdk.CfnParameter, ddb_table: dynamodb.Table)
        : ecsPatterns.ApplicationLoadBalancedFargateService {

        const taskRole = new iam.Role(this, 'CellularRouterTaskRole', {
            assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
            inlinePolicies: {
                'policy': new iam.PolicyDocument({
                    statements: [new iam.PolicyStatement({
                        actions: [
                            "dynamodb:BatchGet*",
                            "dynamodb:DescribeStream",
                            "dynamodb:DescribeTable",
                            "dynamodb:Get*",
                            "dynamodb:Query",
                            "dynamodb:Scan",
                            "dynamodb:BatchWrite*",
                            "dynamodb:Delete*",
                            "dynamodb:Update*",
                            "dynamodb:PutItem"
                        ],
                        resources: ['arn:aws:dynamodb:*:*:table/' + ddb_table.tableName],
                    })],
                })
            }
        });
        const executionRole = new iam.Role(this, 'CellularRouterExecutionRole', {
            assumedBy: new iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
            inlinePolicies: {
                'policy': new iam.PolicyDocument({
                    statements: [new iam.PolicyStatement({
                        actions: [
                            "ecr:GetAuthorizationToken",
                            "ecr:BatchCheckLayerAvailability",
                            "ecr:GetDownloadUrlForLayer",
                            "ecr:BatchGetImage",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents"
                        ],
                        resources: ['*'],
                    })],
                })
            }
        });
        const cluster = new ecs.Cluster(this, 'Cell-Cluster', {
            vpc: vpc,
            clusterName: 'Cell-Cluster-' + cell_id.valueAsString,
        });
        const service = new ecsPatterns.ApplicationLoadBalancedFargateService(
            this, 'Cell-Service', {
                cluster,
                loadBalancerName: "Cell-LoadBalancer-" + cell_id.valueAsString,
                serviceName: "Cell-Service-" + cell_id.valueAsString,
                memoryLimitMiB: 1024,
                cpu: 512,
                minHealthyPercent: 0, // Helps with faster deployments for testing
                taskImageOptions: {
                    image: ecs.ContainerImage.fromRegistry(image_uri.valueAsString),
                    environment: {
                        cellId: cell_id.valueAsString,
                        tableName: ddb_table.tableName,
                        tableArn: ddb_table.tableArn,
                    },
                    containerPort: 8080,
                    taskRole: taskRole,
                    executionRole: executionRole,
                },
                openListener: false,
            });
        service.targetGroup.setAttribute('deregistration_delay.timeout_seconds', '10');

        const lbSecurityGroup = new ec2.SecurityGroup(this, 'lb-security-group', {
            vpc,
            description: 'Allow inbound prefix from the cell prefix list',
            allowAllOutbound: false,
        });
        lbSecurityGroup.addIngressRule(
            ec2.Peer.prefixList(cdk.Fn.importValue('cellsInboundPrefixListId')),
            ec2.Port.tcp(80));
        service.targetGroup.setAttribute('deregistration_delay.timeout_seconds', '10');
        service.loadBalancer.addSecurityGroup(lbSecurityGroup)

        new cdk.CfnOutput(this, 'dnsName', {
            value: service.loadBalancer.loadBalancerDnsName,
        });
        new cdk.CfnOutput(this, 'serviceName', {
            value: service.service.serviceName,
        });
        new cdk.CfnOutput(this, 'clusterName', {
            value: service.cluster.clusterName,
        });
        return service;
    }
}
