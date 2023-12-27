import {
    Stack, StackProps, aws_ecr as ecr, aws_ec2 as ec2, aws_secretsmanager as secretsmanager,
} from 'aws-cdk-lib';
import {Construct} from 'constructs';
import * as cdk from 'aws-cdk-lib';

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

        const prefixList = new ec2.PrefixList(this, 'inboundPrefixList', {
            maxEntries: 20,
        });
        new cdk.CfnOutput(this, 'inboundPrefixListId', {
            value: prefixList.prefixListId,
            exportName: 'cellsInboundPrefixListId'
        });

        this.ssl_secrets()
    }

    ssl_secrets() {
        const privateKeySecret = new secretsmanager.Secret(this, 'PrivateKeySecret', {
            secretName: "cellsJwtPrivateKey",
            secretStringValue: cdk.SecretValue.unsafePlainText("undefined")
        });
        new cdk.CfnOutput(this, 'privateKeyArn', {
            value: privateKeySecret.secretArn,
            exportName: 'cellsPrivate'
        });


        const publicKeySecret = new secretsmanager.Secret(this, 'PublicKeySecret', {
            secretName: "cellsJwtPublicKey",
            secretStringValue: cdk.SecretValue.unsafePlainText("undefined")
        });
        new cdk.CfnOutput(this, 'publicKeyArn', {
            value: publicKeySecret.secretArn,
            exportName: 'cellsPublic'
        });
    }
}
