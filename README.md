# k8s-sqs-autoscaler
Kubernetes pod autoscaler based on queue size in AWS SQS.

This is a fork repo created based on the original work done by Dan Maas: https://github.com/coreplane/k8s-sqs-autoscaler

## Usage
Create a kubernetes deployment like this:
```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-k8s-autoscaler
spec:
  revisionHistoryLimit: 1
  replicas: 1
  template:
    metadata:
      labels:
        app: my-k8s-autoscaler
    spec:
      containers:
      - name: my-k8s-autoscaler
        image: opendatacube/k8s-sqs-autoscaler:1.0.2
        command:
          - ./k8s-sqs-autoscaler
          - --sqs-queue-url=https://sqs.$(AWS_REGION).amazonaws.com/$(AWS_ID)/$(SQS_QUEUE) # required
          - --kubernetes-deployment=$(KUBERNETES_DEPLOYMENT)
          - --kubernetes-namespace=$(K8S_NAMESPACE) # optional
          - --aws-region=us-west-2  #required
          - --poll-period=10 # optional
          - --scale-down-cool-down=30 # optional
          - --scale-up-cool-down=10 # optional
          - --scale-up-messages=20 # optional
          - --scale-down-messages=10 # optional
          - --max-pods=30 # optional
          - --min-pods=1 # optional
        env:
          - name: K8S_NAMESPACE
            valueFrom:
              fieldRef:
                fieldPath: metadata.namespace
        resources:
          requests:
            memory: "64Mi"
            cpu: "250m"
          limits:
            memory: "1512Mi"
            cpu: "500m"
        ports:
        - containerPort: 80

```

## Options
* --sqs-queue-url=queue-url-to-watch # --sqs-queue-url or --sqs-queue-name required
* --sqs-queue-name=sqs-queue-name  # --sqs-queue-url or --sqs-queue-name required
* --kubernetes-deployment=$(KUBERNETES_DEPLOYMENT) # required - deplyment-name-of-scaling-pod
* --kubernetes-namespace=$(K8S_NAMESPACE) # required
* --aws-region=us-west-2 # required
* --poll-period=10 # optional
* --scale-down-cool-down=30 # optional
* --scale-up-cool-down=10 # optional
* --scale-up-messages=20 # optional
* --scale-down-messages=20 # optional
* --max-pods=20 # optional
* --min-pods=1 # optional


## Debugging
Enable environment variable LOGGING_LEVEL with log level of INFO, ERROR, DEBUG
