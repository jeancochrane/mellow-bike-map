# Deployment

## Continuous Integration

We use GitHub Actions to trigger a CodeDeploy deployment to the `production` deployment group
every time a new commit is pushed to the `master` branch. The integration between GitHub
Actions and CodeDeploy was configured using [this
guide](https://aws.amazon.com/blogs/devops/integrating-with-github-actions-ci-cd-pipeline-to-deploy-a-web-app-to-amazon-ec2/).
