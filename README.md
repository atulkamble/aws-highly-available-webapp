# AWS Capstone Project: Highly Available Web Application with Serverless Visitor Tracking



Intermediate AWS Project

Hands-on Deployment



## 1. Project title

Design and Deploy a Highly Available, Scalable and Secure Web Application on AWS with Serverless Visitor Tracking

This project combines AWS services from your training syllabus into one practical, real-world architecture. It covers networking, compute, load balancing, auto scaling, database management, serverless computing, monitoring, security and Infrastructure as Code.

## 2. Project objectives

1. Design a custom AWS VPC with public and private subnets.
2. Deploy web servers using Amazon EC2 and Auto Scaling.
3. Distribute incoming traffic using an Application Load Balancer.
4. Configure Route 53 for domain-based access.
5. Store application data in Amazon RDS MySQL.
6. Track website visitors using AWS Lambda and DynamoDB.
7. Store static assets in Amazon S3.
8. Monitor infrastructure using Amazon CloudWatch.
9. Configure SNS notifications for operational alerts.
10. Automate infrastructure deployment using AWS CloudFormation.

## 3. Real-world use case

Scenario: A company wants to host a product website that can handle increasing visitor traffic without manually adding servers.

When customers visit the website, the application should display product information, retrieve database records, record visits, and remain available even when an individual server fails.

The company also wants automatic scaling, secure networking, monitoring and a repeatable deployment process.

## 4. Project architecture

Logical architecture. The ALB is deployed in public subnets, while EC2 instances and RDS are private. Lambda and DynamoDB represent the visitor-tracking component.

Additional supporting services: S3 for static assets, CloudWatch for monitoring, SNS for notifications, IAM for access control, CloudTrail for auditing, and CloudFormation for provisioning.

## 5. AWS services used and why

| AWS service               | Purpose and significance                                   |
| ------------------------- | ---------------------------------------------------------- |
| VPC                       | Provides an isolated networking environment                |
| Public/private subnets    | Separate internet-facing and internal resources            |
| Internet Gateway          | Enables internet connectivity for public resources         |
| NAT Gateway               | Provides outbound internet access to private EC2 instances |
| EC2                       | Hosts the web application                                  |
| Application Load Balancer | Distributes HTTP traffic across healthy servers            |
| Auto Scaling              | Automatically adjusts EC2 capacity                         |
| Route 53                  | Maps the website domain to the ALB                         |
| RDS MySQL                 | Stores relational application data                         |
| Lambda                    | Runs visitor-tracking logic without managing servers       |
| DynamoDB                  | Stores visitor counters using a NoSQL database             |
| S3                        | Stores static website assets                               |
| IAM                       | Controls service permissions                               |
| CloudWatch                | Collects metrics, logs and alarms                          |
| SNS                       | Sends notifications                                        |
| CloudTrail                | Records AWS API activity                                   |
| CloudFormation            | Deploys infrastructure from code                           |

## 6. Application workflow

1. User opens `www.example.com`.
2. Route 53 resolves the domain to the Application Load Balancer.
3. ALB forwards the request to a healthy EC2 instance.
4. The web application retrieves product information from RDS MySQL.
5. The application invokes Lambda to update the visitor count in DynamoDB.
6. The web page displays product details and the visitor count.
7. Auto Scaling adjusts EC2 capacity based on configured demand metrics.
8. CloudWatch monitors resources and triggers SNS alerts when alarm thresholds are met.

## 7. Project code and deployment

I have prepared a downloadable starter project containing a working CloudFormation lab for EC2, Application Load Balancer, Auto Scaling, Lambda and DynamoDB.

AWS Capstone Project

ZIP · CloudFormation YAML, Python application and README

&#x20;Download Project ZIP

### Project folder structure

```
aws-capstone/
├── README.md
├── infra/
│   └── template.yaml
└── app/
    └── server.py
```

### Deployment commands

Step 1 — Validate the template

```
aws cloudformation validate-template \
  --template-body file://infra/template.yaml
```

Step 2 — Deploy the infrastructure

```
aws cloudformation deploy \
  --stack-name aws-capstone \
  --template-file infra/template.yaml \
  --capabilities CAPABILITY_IAM \
  --region us-east-1
```

Step 3 — Retrieve the website URL

```
aws cloudformation describe-stacks \
  --stack-name aws-capstone \
  --query 'Stacks[0].Outputs' \
  --region us-east-1
```

Step 4 — Test the application

Open the website URL and refresh the page. The Lambda function increments the visitor counter in DynamoDB.

Step 5 — Delete resources after practice

```
aws cloudformation delete-stack \
  --stack-name aws-capstone \
  --region us-east-1
```

## 8. Project implementation phases

| Phase | Implementation                 | Expected result                      |
| ----- | ------------------------------ | ------------------------------------ |
| 1     | VPC, subnets and routing       | Network configured                   |
| 2     | EC2, ALB and Auto Scaling      | Highly available website             |
| 3     | Lambda and DynamoDB            | Visitor counter working              |
| 4     | RDS MySQL and S3               | Database and static storage          |
| 5     | Route 53 and HTTPS             | Domain-based secure access           |
| 6     | CloudWatch, SNS and CloudTrail | Monitoring, alerts and auditing      |
| 7     | CloudFormation and testing     | Repeatable infrastructure deployment |

Implementation note: The downloadable code covers phases 1–3 as a simplified lab, using public-subnet EC2 instances. Phases 4–7 are planned extensions for the full architecture. The starter project has not been deployed or live-tested in an AWS account. AWS usage charges may apply.

## 9. Expected learning outcomes

After completing the full project, students should be able to explain and demonstrate AWS networking, high availability, auto scaling, relational and NoSQL databases, serverless integration, infrastructure automation, security and monitoring.

Recommended final deliverables: Architecture diagram, source code, deployed website URL, infrastructure screenshots, test results and a short project demonstration.
