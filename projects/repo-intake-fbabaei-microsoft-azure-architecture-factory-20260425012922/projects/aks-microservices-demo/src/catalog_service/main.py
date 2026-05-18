from fastapi import FastAPI, HTTPException

from shared_lib import HealthStatus, Product, get_settings


app = FastAPI(title="AKS Demo - Catalog Service")
settings = get_settings()

PRODUCTS = [
    Product(sku="SKU-1001", name="Kubernetes Handbook", category="Books", description="Practical AKS and Kubernetes operations guide.", price=49.0),
    Product(sku="SKU-1002", name="Platform SRE Guide", category="Books", description="Reliability patterns for platform engineering teams.", price=79.0),
    Product(sku="SKU-1003", name="Cloud Native Patterns", category="Books", description="Reference patterns for microservice delivery on Azure.", price=59.0),
    Product(sku="SKU-1004", name="AKS Cost Dashboard", category="Software", description="Dashboard starter kit for container cost visibility.", price=129.0),
]


@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(service="catalog-service", environment=settings.environment)


@app.get("/products", response_model=list[Product])
def list_products() -> list[Product]:
    return PRODUCTS


@app.get("/products/{sku}", response_model=Product)
def get_product(sku: str) -> Product:
    for product in PRODUCTS:
        if product.sku == sku:
            return product
    raise HTTPException(status_code=404, detail="Product not found")
