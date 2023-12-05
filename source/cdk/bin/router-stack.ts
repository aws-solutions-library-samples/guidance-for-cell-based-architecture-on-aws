import {
    Stack, StackProps, aws_ecs_patterns as ecsPatterns, aws_ecs as ecs, aws_ec2 as ec2,
    aws_s3 as s3, aws_stepfunctions as sfn, aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions, aws_iam as iam, aws_dynamodb as dynamodb, aws_lambda as lambda,
    aws_kinesis as kinesis
} from 'aws-cdk-lib';
import * as firehose from '@aws-cdk/aws-kinesisfirehose-alpha';
import * as firehose_destinations from '@aws-cdk/aws-kinesisfirehose-destinations-alpha';
import {Construct} from 'constructs';
import * as cdk from 'aws-cdk-lib';
import * as fs from 'fs';
import * as path from 'path';
import { DefinitionBody } from 'aws-cdk-lib/aws-stepfunctions';

export class RouterStack extends Stack {
    constructor(scope: Construct, id: string, props?: StackProps) {
        super(scope, id, props);

        const image_uri = new cdk.CfnParameter(this, "image_uri", {
            type: "String",
            description: "URI of the repository",
        });

        const vpc = new ec2.Vpc(this, 'Router-VPC', {
            vpcName: "CellRouter-VPC",
            ipAddresses: ec2.IpAddresses.cidr("10.0.0.0/16"),
            natGateways: 1 // For testing only
        })

        const cells_table = new dynamodb.Table(this, 'Cells-Table', {
            tableName: 'Cellular-Routing-Cells',
            partitionKey: {name: 'cell_id', type: dynamodb.AttributeType.STRING},
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            removalPolicy: cdk.RemovalPolicy.DESTROY,
        })
        new cdk.CfnOutput(this, 'cellsTable', {
            value: cells_table.tableName,
        });

        const users_table = new dynamodb.Table(this, 'Users-Table', {
            tableName: 'Cellular-Routing-Users',
            partitionKey: {name: 'username', type: dynamodb.AttributeType.STRING},
            billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
            removalPolicy: cdk.RemovalPolicy.DESTROY,
        })
        new cdk.CfnOutput(this, 'usersTable', {
            value: users_table.tableName,
        });

        const bucket = this.bucket();

        const updateCellsSm = this.createAndUpdateStatemachines()

        this.ecsService(vpc, image_uri, cells_table, users_table)

        const checkCanarySm = this.checkcanaryStatemachine()

        const pipelineLambda = this.pipelineLambda(cells_table, bucket, updateCellsSm)

        this.codePipeline(bucket, updateCellsSm, checkCanarySm, pipelineLambda)

        this.tokenLambda()

        this.dataLakeStream(bucket)
    }

    bucket(): s3.Bucket {
        const bucket = new s3.Bucket(this, 'bucket', {
            bucketName: 'cellular-arch-' + cdk.Stack.of(this).account + '-' + cdk.Stack.of(this).region,
            removalPolicy: cdk.RemovalPolicy.DESTROY,
            autoDeleteObjects: true,
            versioned: true,
        });

        new cdk.CfnOutput(this, 'bucketName', {
            value: bucket.bucketName,
        });
        new cdk.CfnOutput(this, 'bucketRegionalDomainName', {
            value: bucket.bucketRegionalDomainName,
        });
        return bucket
    }

    ecsService(vpc: ec2.Vpc, image_uri: cdk.CfnParameter, cells_table: dynamodb.Table, users_table: dynamodb.Table)
        : ecsPatterns.ApplicationLoadBalancedFargateService {
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
                        resources: [
                            'arn:aws:dynamodb:*:*:table/' + cells_table.tableName,
                            'arn:aws:dynamodb:*:*:table/' + users_table.tableName,
                        ],
                    }), new iam.PolicyStatement({
                        actions: [
                            "cloudformation:DescribeStacks",
                        ],
                        resources: [
                            '*'
                        ],
                    })],
                })
            }
        });


        const cluster = new ecs.Cluster(this, 'Cell-Cluster', {
            vpc: vpc,
            clusterName: 'Cell-Router',
        });
        const service = new ecsPatterns.ApplicationLoadBalancedFargateService(
            this, 'CellRouter-Service', {
                cluster,
                loadBalancerName: "CellRouter-LoadBalancer",
                serviceName: "CellRouter-Service",
                memoryLimitMiB: 1024,
                cpu: 512,
                minHealthyPercent: 0, // Helps with faster deployments for testing
                taskImageOptions: {
                    image: ecs.ContainerImage.fromRegistry(image_uri.valueAsString),
                    environment: {
                        cellsTableName: cells_table.tableName,
                        usersTableName: users_table.tableName,
                    },
                    containerPort: 8080,
                    executionRole,
                    taskRole,
                },
                openListener: false,
            });
        
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

        new cdk.CfnOutput(this, 'serviceName', {
            value: service.service.serviceName,
        });
        new cdk.CfnOutput(this, 'clusterName', {
            value: service.cluster.clusterName,
        });
        new cdk.CfnOutput(this, 'dnsName', {
            value: service.loadBalancer.loadBalancerDnsName,
        });

        return service;
    }

    codePipeline(bucket: s3.Bucket,
                 updateCellsSm: sfn.StateMachine,
                 checkCanarySm: sfn.StateMachine,
                 pipelineLambda: lambda.Function) {
        const pipeline = new codepipeline.Pipeline(this, 'CellPipeline', {
            pipelineName: 'CellPipeline'
        })

        const sourceOutput = new codepipeline.Artifact();
        pipeline.addStage({
            stageName: 'Source',
            actions: [new codepipeline_actions.S3SourceAction({
                actionName: 'S3Source',
                bucket: bucket,
                bucketKey: 'template_cell.yaml',
                output: sourceOutput,
            })],
        });

        pipeline.addStage({
            stageName: 'DeployToSandbox',
            actions: [new codepipeline_actions.StepFunctionInvokeAction({
                actionName: 'Invoke',
                stateMachine: updateCellsSm,
                stateMachineInput: codepipeline_actions.StateMachineInput.literal(
                    {
                        cellIds: ['sandbox'],
                        templateUrl: 'https://' + bucket.bucketRegionalDomainName + '/template_cell.yaml',
                    }),
            })],
        });

        pipeline.addStage({
            stageName: 'CheckCanaryForSandbox',
            actions: [new codepipeline_actions.StepFunctionInvokeAction({
                actionName: 'Invoke',
                stateMachine: checkCanarySm,
                stateMachineInput: codepipeline_actions.StateMachineInput.literal(
                    {
                        cellIds: ['sandbox'],
                        waitseconds: 360,
                    }),
            })],
        });

        pipeline.addStage({
            stageName: 'DeployToOtherCells',
            actions: [new codepipeline_actions.LambdaInvokeAction({
                actionName: 'Invoke',
                lambda: pipelineLambda,
                variablesNamespace: 'cells',
                userParameters: {
                    'action': 'ALL_ACTIVE_EXCEPT_SANDBOX'
                }
            })],
        });
    }

    pipelineLambda(cells_table: dynamodb.Table, bucket: s3.Bucket, updateCellsFunction: sfn.StateMachine) {
        const role = new iam.Role(this, 'CellLambdaRole', {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
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
                        resources: [
                            'arn:aws:dynamodb:*:*:table/' + cells_table.tableName,
                        ],
                    }), new iam.PolicyStatement({
                        actions: [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        resources: [
                            '*',
                        ],
                    }), new iam.PolicyStatement({
                        actions: [
                            "states:StartExecution",
                        ],
                        resources: [
                            updateCellsFunction.stateMachineArn
                        ],
                    })
                    ],
                })
            }
        });

        return new lambda.Function(this, 'CellPipelineLambda', {
            functionName: 'cellPipelineLambda',
            //code: lambda.Code.fromAsset(path.join(__dirname, '../lambda/cells_for_codepipeline'), {
            code: lambda.Code.fromAsset(path.join(__dirname, '../../cells_for_codepipeline'), {
                bundling: {
                    image: lambda.Runtime.PYTHON_3_9.bundlingImage,
                    command: [
                        'bash', '-c',
                        'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output'
                    ],
                },
            }),
            runtime: lambda.Runtime.PYTHON_3_9,
            handler: 'handler.handler',
            role: role,
            environment: {
                'cellsTable': cells_table.tableName,
                'templateUrl': 'https://' + bucket.bucketRegionalDomainName + '/template_cell.yaml',
                'updateCellsFunctionArn': updateCellsFunction.stateMachineArn,
                'templateBucketName': bucket.bucketRegionalDomainName,
            }
        });
    }

    tokenLambda() {
        const role = new iam.Role(this, 'CanaryTokenLambdaRole', {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
            inlinePolicies: {
                'policy': new iam.PolicyDocument({
                    statements: [new iam.PolicyStatement({
                        actions: [
                            "logs:CreateLogGroup",
                            "logs:CreateLogStream",
                            "logs:PutLogEvents",
                        ],
                        resources: [
                            '*',
                        ],
                    })
                    ],
                })
            }
        });

        return new lambda.Function(this, 'CanaryTokenLambda', {
            functionName: 'cellCanaryToken',
            code: lambda.Code.fromAsset(path.join(__dirname, '../canary-token-lambda'), {
                bundling: {
                    image: lambda.Runtime.PYTHON_3_9.bundlingImage,
                    command: [
                        'bash', '-c',
                        'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output'
                    ],
                },
            }),
            runtime: lambda.Runtime.PYTHON_3_9,
            handler: 'canary-token.handler',
            role: role,
            environment: {
            }
        });
    }

    createAndUpdateStatemachines(): sfn.StateMachine {
        const deploymentRole = new iam.Role(this, 'CellularRouterSfnRole', {
            assumedBy: new iam.ServicePrincipal('states.amazonaws.com'),
            roleName: 'CellBasedSfnRole',
            inlinePolicies: {
                'policy': new iam.PolicyDocument({
                    statements: [new iam.PolicyStatement({
                        actions: [
                            "cloudformation:*",
                            "s3:*",
                            "ssm:GetParameters",
                            "ec2:*",
                            "dynamodb:*",
                            "ecs:*",
                            "iam:*",
                            "logs:*",
                            "elasticloadbalancingv2:*",
                            "elasticloadbalancing:*",
                            "states:*",
                            "synthetics:*",
                            "lambda:*",
                            "kinesis:*",
                            "codepipeline:PutJobSuccessResult",
                            "codepipeline:PutJobFailureResult",
                        ],
                        resources: ['*'],
                    })],
                })
            }
        });

        const createCellFunction = this.create_statemachine(
            'CreateCellSfn',
            'Cellular-Create-Cell',
            'sfn_create_cell.asl.json',
            deploymentRole);
        new cdk.CfnOutput(this, 'create-cell-function', {
            value: createCellFunction.stateMachineArn,
        });

        const updateStatemachine = this.create_statemachine(
            'UpdateCellsSfn',
            'Cellular-Update-Cells',
            'sfn_update_cell.asl.json',
            deploymentRole);

        new cdk.CfnOutput(this, 'update-cells-function', {
            value: updateStatemachine.stateMachineArn,
        });

        return updateStatemachine
    }

    checkcanaryStatemachine() {
        const role = new iam.Role(this, 'CellularRouterSfnCanaryRole', {
            assumedBy: new iam.ServicePrincipal('states.amazonaws.com'),
            roleName: 'CellBasedSfnCanaryRole',
            inlinePolicies: {
                'policy': new iam.PolicyDocument({
                    statements: [new iam.PolicyStatement({
                        actions: [
                            "logs:*",
                            "states:*",
                            "synthetics:*",
                            "codepipeline:PutJobSuccessResult",
                            "codepipeline:PutJobFailureResult",
                        ],
                        resources: ['*'],
                    })],
                })
            }
        });

        const statemachine = this.create_statemachine(
            'CellsCanarySfn',
            'Cellular-CheckCanary',
            'sfn_check_canary.asl.json',
            role);

        new cdk.CfnOutput(this, 'check-canary-statemachine', {
            value: statemachine.stateMachineArn,
        });

        return statemachine
    }

    create_statemachine(constructName: string, sfnName: string, fileName: string,
                                role: iam.Role) {
        const file = fs.readFileSync('./statemachines/' + fileName);
        const statemachine = new sfn.StateMachine(this, constructName, {
            stateMachineName: sfnName,
            definitionBody: DefinitionBody.fromChainable(new sfn.Pass(this, constructName + 'StartState')),
            role: role,
        });
        const cfnStatemachine = statemachine.node.defaultChild as sfn.CfnStateMachine;
        cfnStatemachine.definitionString = file.toString();
        return statemachine;
    }

    dataLakeStream(bucket: s3.Bucket) {
        const stream = new kinesis.Stream(this, 'cellDataLakeStream', {
            streamName: 'cell-datalake-stream',
        });

        new cdk.CfnOutput(this, 'dataLakeStream', {
            value: stream.streamArn,
            exportName: 'cellDataLakeArn'
        });

        new firehose.DeliveryStream(this, 'Delivery Stream', {
            sourceStream: stream,
            destinations: [new firehose_destinations.S3Bucket(bucket, {
                dataOutputPrefix: 'datalake',
            })],
        });
    }
}
