import logging
import os

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.client.models.v1_deployment import V1Deployment
from src.schedules.models import DeploymentInfo
from src.shared.settings import settings


class K8sClient:
    """Kubernetes client wrapper"""

    apps_v1: client.AppsV1Api
    core_v1: client.CoreV1Api
    FLUXCD_ANNOTATION_KEY: str = "kustomize.toolkit.fluxcd.io/reconcile"
    ARGOCD_ANNOTATION_KEY: str = "argocd.argoproj.io/skip-reconcile"

    def __init__(self):
        """Initialize Kubernetes client."""
        self.__logger = logging.getLogger(__name__)
        try:
            config.load_incluster_config() if os.getenv("KUBERNETES_SERVICE_HOST") else config.load_kube_config()
        except Exception as e:
            self.__logger.critical(e)
        self.apps_v1 = client.AppsV1Api()
        self.core_v1 = client.CoreV1Api()

    # def list_namespaces(self) -> list[str]:
    #     """List all namespaces"""
    #     try:
    #         namespaces = self.core_v1.list_namespace()
    #         return [ns.metadata.name for ns in namespaces.items]
    #     except ApiException as e:
    #         raise Exception(f"Failed to list namespaces: {e}")

    def list_allowed_namespaces(self, label_key: str, label_value: str) -> list[str]:
        """List only namespaces with specific label"""
        try:
            label_selector = f"{label_key}={label_value}"
            namespaces = self.core_v1.list_namespace(label_selector=label_selector)
            return [ns.metadata.name for ns in namespaces.items]
        except ApiException as e:
            raise Exception(f"Failed to list allowed namespaces: {e}")

    def is_namespace_allowed(self, namespace: str, label_key: str, label_value: str) -> bool:
        """Check if a namespace has the required label"""
        try:
            ns = self.core_v1.read_namespace(namespace)
            labels = ns.metadata.labels or {}
            return labels.get(label_key) == label_value
        except ApiException:
            return False

    def list_deployments(self, namespace: str) -> list[DeploymentInfo]:
        """List all deployments in a namespace"""
        try:
            deployments = self.apps_v1.list_namespaced_deployment(namespace)
            result = []
            for deploy in deployments.items:
                info = DeploymentInfo(
                    name=deploy.metadata.name,
                    namespace=deploy.metadata.namespace,
                    replicas=deploy.spec.replicas or 0,
                    available_replicas=deploy.status.available_replicas or 0,
                )
                result.append(info)
            return result
        except ApiException as e:
            raise Exception(f"Failed to list deployments: {e}")

    def get_deployment(self, namespace: str, name: str) -> V1Deployment:
        """Get a specific deployment"""
        try:
            return self.apps_v1.read_namespaced_deployment(name, namespace)
        except ApiException as e:
            raise Exception(f"Failed to get deployment {name} in namespace {namespace}: {e}")

    def get_deployment_replicas(self, namespace: str, name: str) -> int:
        """Get current replica count of a deployment"""
        try:
            deployment = self.get_deployment(namespace, name)
            return deployment.spec.replicas or 0
        except Exception as e:
            raise Exception(f"Failed to get replicas for deployment {name}: {e}")

    def scale_deployment(self, namespace: str, name: str, replicas: int) -> None:
        """Scale a deployment to specified replicas"""
        try:
            deployment = self.get_deployment(namespace=namespace, name=name)
            annotations = dict(deployment.metadata.annotations) if deployment.metadata.annotations else {}

            if settings.FLUXCD_OPTION:
                if replicas == 0:
                    self.__logger.info(f"Scaling down {namespace}/{name}, setting FluxCD annotation to disabled")
                    annotations[self.FLUXCD_ANNOTATION_KEY] = "disabled"
                else:
                    if annotations.get(self.FLUXCD_ANNOTATION_KEY):
                        self.__logger.info(f"Scaling up {namespace}/{name}, removing FluxCD annotation")
                        annotations.pop(self.FLUXCD_ANNOTATION_KEY, None)

            if settings.ARGOCD_OPTION:
                if replicas == 0:
                    self.__logger.info(f"Scaling down {namespace}/{name}, setting ArgoCD annotation to true")
                    annotations[self.ARGOCD_ANNOTATION_KEY] = "true"
                else:
                    if annotations.get(self.ARGOCD_ANNOTATION_KEY):
                        self.__logger.info(f"Scaling up {namespace}/{name}, removing ArgoCD annotation")
                        annotations.pop(self.ARGOCD_ANNOTATION_KEY, None)

            deployment.metadata.annotations = annotations
            deployment.spec.replicas = replicas
            self.apps_v1.replace_namespaced_deployment(
                name=name,
                namespace=namespace,
                body=deployment
            )
        except Exception as e:
            raise Exception(f"Failed to scale deployment {name} to {replicas} replicas: {e}")

    def scale_down(self, namespace: str, name: str) -> None:
        """Scale down deployment to 0 replicas"""
        self.__logger.info(f"Scaling down deployment {namespace}/{name} to 0 replicas")
        self.scale_deployment(namespace=namespace, name=name, replicas=0)

    def scale_up(self, namespace: str, name: str, replicas: int) -> None:
        """Scale up deployment to specified replicas"""
        self.__logger.info(f"Scaling up deployment {namespace}/{name} to {replicas} replicas")
        self.scale_deployment(namespace=namespace, name=name, replicas=replicas)


# Global instance
k8s_client: K8sClient | None = None


def get_k8s_client() -> K8sClient:
    """Get or create Kubernetes client instance"""
    global k8s_client
    if k8s_client is None:
        k8s_client = K8sClient()
    return k8s_client
