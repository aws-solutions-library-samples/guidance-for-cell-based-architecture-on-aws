#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import {CellStack} from './cell-stack';
import {ReposStack} from './repos-stack';
import {RouterStack} from './router-stack';
import {Tags} from 'aws-cdk-lib';

const app = new cdk.App();

new ReposStack(app, 'Cellular-Repos', {
    env: {account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION},
});

const cellStack = new CellStack(app, 'Cellular-Cell-sandbox', {
    env: {account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION},
});
Tags.of(cellStack).add('auto-delete', 'no')

const routerStack = new RouterStack(app, 'Cellular-Router', {
    env: {account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION},
});
Tags.of(routerStack).add('auto-delete', 'no')