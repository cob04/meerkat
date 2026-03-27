from celery import shared_task


@shared_task(queue="cdc")
def run_cdc_consumer():
    from apps.cdc.consumer import run_consumer

    run_consumer()
