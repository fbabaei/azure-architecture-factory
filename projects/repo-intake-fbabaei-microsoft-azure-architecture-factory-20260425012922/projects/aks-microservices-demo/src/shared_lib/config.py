import os
from functools import lru_cache
from pydantic import BaseModel


class ServiceEndpoints(BaseModel):
    catalog_url: str
    order_url: str
    payment_url: str


class Settings(BaseModel):
    service_name: str = "api-gateway"
    environment: str = "dev"

    catalog_url: str = "http://catalog-service"
    order_url: str = "http://order-service"
    payment_url: str = "http://payment-service"

    def endpoints(self) -> ServiceEndpoints:
        return ServiceEndpoints(
            catalog_url=self.catalog_url,
            order_url=self.order_url,
            payment_url=self.payment_url,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        service_name=os.getenv("AKS_DEMO_SERVICE_NAME", "api-gateway"),
        environment=os.getenv("AKS_DEMO_ENVIRONMENT", "dev"),
        catalog_url=os.getenv("AKS_DEMO_CATALOG_URL", "http://catalog-service"),
        order_url=os.getenv("AKS_DEMO_ORDER_URL", "http://order-service"),
        payment_url=os.getenv("AKS_DEMO_PAYMENT_URL", "http://payment-service"),
    )
