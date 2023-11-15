import json
import logging
import boto3
from cell_lib import CellClient

logger = logging.getLogger()
logger.setLevel(logging.INFO)

codepipeline = boto3.client('codepipeline')
stepfunction = boto3.client('stepfunctions')

cellClient = CellClient()


def handler(event, context):
    logger.info(json.dumps(event))
    job_id = event['CodePipeline.job']['id']
    try:
        cellClient.update_cells(job_id)
    except Exception as error:
        logger.exception(error)
        response = codepipeline.put_job_failure_result(
            jobId=job_id,
            failureDetails={
                'type': 'JobFailed',
                'message': f'{error.__class__.__name__}: {str(error)}'
            }
        )
        logger.debug(response)
