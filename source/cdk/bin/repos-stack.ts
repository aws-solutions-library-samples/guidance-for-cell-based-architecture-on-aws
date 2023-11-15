import {
    Stack, StackProps, aws_ecr as ecr, aws_s3 as s3, aws_lambda as lambda, aws_s3_deployment as s3_deploy
} from 'aws-cdk-lib';
import {Construct} from 'constructs';
import * as cdk from 'aws-cdk-lib';
import {Asset} from 'aws-cdk-lib/aws-s3-assets';
import * as path from 'path';

export class ReposStack extends Stack {
    constructor(scope: Construct, id: string, props?: StackProps) {
        super(scope, id, props);

        const repoCell = new ecr.Repository(this, 'RepoCell', {
            repositoryName: 'cellular_cell',
            imageScanOnPush: true,
        });

        new cdk.CfnOutput(this, 'repoCellUri', {
            value: repoCell.repositoryUri,
            exportName: 'repoCellUri'
        });

        const repoRouting = new ecr.Repository(this, 'RepoRouting', {
            repositoryName: 'cellular_routing',
            imageScanOnPush: true,
        });

        new cdk.CfnOutput(this, 'repoRoutingUri', {
            value: repoRouting.repositoryUri,
            exportName: 'repoRoutingUri'
        });
    }
}
