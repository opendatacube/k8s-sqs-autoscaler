import boto3
from time import sleep, time
from logs.log import logger
from kubernetes import client, config

class SQSPoller:

    options = None
    sqs_client = None
    extensions_v1_beta1 = None
    last_message_count = None

    def __init__(self, options):
        self.options = options
        self.sqs_client = boto3.client('sqs')

        if not self.options.sqs_queue_url:
            # derive the URL from the queue name
            self.options.sqs_queue_url = self.sqs_client.get_queue_url(QueueName = self.options.sqs_queue_name)['QueueUrl']

        config.load_incluster_config()
        self.extensions_v1_beta1 = client.ExtensionsV1beta1Api()
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
        logger.debug("Current message counts: %d visible / %d invisible" % (message_count, invisible_message_count))
        deployment = self.deployment()
        logger.debug("Current replicas: %d" %  deployment.spec.replicas)
        t = time()
        if  message_count >= self.options.scale_up_messages:
            if t - self.last_scale_up_time > self.options.scale_up_cool_down:
                self.scale_up(deployment)
                self.last_scale_up_time = t
            else:
                logger.debug("Waiting for scale up cooldown")
        if message_count <= self.options.scale_down_messages:
            # special case - do not scale to zero unless there are no invisible messages
            if deployment.spec.replicas <= 1 and invisible_message_count > 0:
                logger.debug("Not scaling to zero because messages are still in-flight")
            elif t - self.last_scale_down_time > self.options.scale_down_cool_down:
                self.scale_down(deployment)
                self.last_scale_down_time = t
            else:
                logger.debug("Waiting for scale down cooldown")

        # code for scale to use msg_count
        sleep(self.options.poll_period)

    def scale_up(self, deployment):
        if deployment.spec.replicas < self.options.max_pods:
            logger.info("Scaling up")
            deployment.spec.replicas += 1
            self.update_deployment(deployment)
        elif deployment.spec.replicas > self.options.max_pods:
            self.scale_down(deployment)
        else:
            logger.info("Max pods reached")

    def scale_down(self, deployment):
        if deployment.spec.replicas > self.options.min_pods:
            logger.info("Scaling Down")
            deployment.spec.replicas -= 1
            self.update_deployment(deployment)
        elif deployment.spec.replicas < self.options.min_pods:
            self.scale_up(deployment)
        else:
            logger.info("Min pods reached")

    def deployment(self):
        logger.debug("loading deployment: {} from namespace: {}".format(self.options.kubernetes_deployment, self.options.kubernetes_namespace))
        if self.options.kubernetes_deployment_selector:
            selector = self.options.kubernetes_deployment_selector
        else:
            selector = "app={}".format(self.options.kubernetes_deployment)
        deployments = self.extensions_v1_beta1.list_namespaced_deployment(self.options.kubernetes_namespace, label_selector=selector)
        return deployments.items[0]

    def update_deployment(self, deployment):
        # Update the deployment
        api_response = self.extensions_v1_beta1.patch_namespaced_deployment(
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
