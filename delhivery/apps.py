from django.apps import AppConfig


class DelhiveryConfig(AppConfig):
    name = 'delhivery'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        from orders.plugins import order_confirmed_registry
        from delhivery.tasks import create_shipment_for_order

        from core.features import is_enabled

        #register a hook that enqueues the async Celery task when an order is CONFIRMED,
        #unless Delivery Integration is switched OFF in Site settings
        def _enqueue_shipment(order):
            if is_enabled("delivery_integration"):
                create_shipment_for_order.delay(order_id=order.pk)

        order_confirmed_registry.register(_enqueue_shipment)
