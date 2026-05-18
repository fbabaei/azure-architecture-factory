// Parameter file for development environment
using '../main.bicep'

param environment = 'dev'
param location = 'eastus'
param projectName = 'ai-agent'
param containerImageUri = 'mcr.microsoft.com/azure-app-service/defaultsite:latest'
param containerPort = 8000
