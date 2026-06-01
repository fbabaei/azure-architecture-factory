param(
    [Parameter(Mandatory = $true)]
    [string]$AcrLoginServer,

    [Parameter(Mandatory = $false)]
    [string]$Tag = 'dev',

    [Parameter(Mandatory = $false)]
    [string]$ProjectRoot = 'c:/Users/fbabaei/workspace/azure-architecture-factory/projects/aks-microservices-demo'
)

$ErrorActionPreference = 'Stop'

$services = @(
    @{ Name = 'api-gateway'; Dockerfile = 'src/api_gateway/Dockerfile' },
    @{ Name = 'catalog-service'; Dockerfile = 'src/catalog_service/Dockerfile' },
    @{ Name = 'order-service'; Dockerfile = 'src/order_service/Dockerfile' },
    @{ Name = 'payment-service'; Dockerfile = 'src/payment_service/Dockerfile' }
)

Push-Location $ProjectRoot
try {
    foreach ($service in $services) {
        $image = "$AcrLoginServer/$($service.Name):$Tag"
        Write-Host "Building $image"
        docker build -f $service.Dockerfile -t $image .
        Write-Host "Pushing $image"
        docker push $image
    }
}
finally {
    Pop-Location
}
