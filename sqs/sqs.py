from helper.assume_role_helper import get_autorefresh_session
from time import sleep, time
from logs.log import logger
from kubernetes import client, config
import boto3
import os

class SQSPoller:

    options = None
    sqs_client = None
    apps_v1 = None
    last_message_count = None

    def __init__(self, options):
        self.options = options
        if 'AWS_ROLE_ARN' in os.environ and 'AWS_WEB_IDENTITY_TOKEN_FILE' in os.environ:
            # setup role/session based client
            role_with_web_identity_params = {
                "DurationSeconds": os.getenv('SESSION_DURATION', 3600),
                "RoleArn": os.getenv('AWS_ROLE_ARN'),
                "RoleSessionName": os.getenv('AWS_SESSION_NAME', 'test_session'),
                "WebIdentityToken": open(os.getenv('AWS_WEB_IDENTITY_TOKEN_FILE')).read(),
            }
            autorefresh_session = get_autorefresh_session(**role_with_web_identity_params)
            self.sqs_client = autorefresh_session.client('sqs')
        else:
            self.sqs_client = boto3.client('sqs')

        if not self.options.sqs_queue_url:
            # derive the URL from the queue name
            self.options.sqs_queue_url = self.sqs_client.get_queue_url(QueueName = self.options.sqs_queue_name)['QueueUrl']

        config.load_incluster_config()
        self.apps_v1 = client.AppsV1Api()
        self.last_scale_up_time = time()
        self.last_scale_down_time = time()

    def message_counts(self):
        response = self.sqs_client.get_queue_attributes(
            QueueUrl=self.options.sqs_queue_url,
            AttributeNames=['ApproximateNumberOfMessages','ApproximateNumberOfMessagesNotVisible']
        )
        message_count = int(response['Attributes']['ApproximateNumberOfMessages'])
        invisible_message_count = int(response['Attributes']['ApproximateNumberOfMessagesNotVisible'])
        return message_count, invisible_message_count

    def poll(self):
        message_count, invisible_message_count = self.message_counts()
        deployment = self.deployment()
        logger.debug("Current message counts: %d visible / %d invisible. %d replicas." % (message_count, invisible_message_count, deployment.spec.replicas))
        t = time()
        if  message_count >= self.options.scale_up_messages:
            if t - self.last_scale_up_time > self.options.scale_up_cool_down:
                self.scale_up(deployment)
                self.last_scale_up_time = t
            else:
                logger.debug("Waiting for scale up cooldown")
        if message_count <= self.options.scale_down_messages:
            # special case - do not scale to zero unless there are no invisible messages
            if invisible_message_count > 0 and deployment.spec.replicas <= invisible_message_count:
                logger.debug("Not scaling down because messages are still in-flight")
            elif t - self.last_scale_down_time > self.options.scale_down_cool_down:
                self.scale_down(deployment)
                self.last_scale_down_time = t
            else:
                if deployment.spec.replicas > self.options.min_pods:
                    logger.debug("Waiting for scale down cooldown")

        # code for scale to use msg_count
        sleep(self.options.poll_period)

    def scale_up(self, deployment):
        if deployment.spec.replicas < self.options.max_pods:
            deployment.spec.replicas += 1
            logger.info("Scaling up to %d" % deployment.spec.replicas)
            self.update_deployment(deployment)
        elif deployment.spec.replicas > self.options.max_pods:
            self.scale_down(deployment)
        else:
            logger.debug("Max pods reached")

    def scale_down(self, deployment):
        if deployment.spec.replicas > self.options.min_pods:
            deployment.spec.replicas -= 1
            logger.info("Scaling down to %d" % deployment.spec.replicas)
            self.update_deployment(deployment)
        elif deployment.spec.replicas < self.options.min_pods:
            self.scale_up(deployment)
        else:
            logger.debug("Min pods reached")

    def deployment(self):
        #logger.debug("loading deployment: {} from namespace: {}".format(self.options.kubernetes_deployment, self.options.kubernetes_namespace))
        if self.options.kubernetes_deployment_selector:
            selector = self.options.kubernetes_deployment_selector
        else:
            selector = "app={}".format(self.options.kubernetes_deployment)
        deployments = self.apps_v1.list_namespaced_deployment(self.options.kubernetes_namespace, label_selector=selector)
        return deployments.items[0]

    def update_deployment(self, deployment):
        # Update the deployment
        api_response = self.apps_v1.patch_namespaced_deployment(
            name=self.options.kubernetes_deployment,
            namespace=self.options.kubernetes_namespace,
            body=deployment)
        logger.debug("Deployment updated. status='%s'" % str(api_response.status))

    def run(self):
        options = self.options
        logger.debug("Starting poll for {} every {}s".format(options.sqs_queue_url, options.poll_period))
        while True:
            self.poll()

def run(options):
    """
    poll_period is set as as part of k8s deployment env variable
    sqs_queue_url is set as as part of k8s deployment env variable
    """
    SQSPoller(options).run()
