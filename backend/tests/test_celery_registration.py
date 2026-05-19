def test_celery_registers_project_tasks():
    from app.workers.celery_app import celery_app

    assert "document_process" in celery_app.tasks
    assert "report_analyze" in celery_app.tasks
    assert "report_generate" in celery_app.tasks
    assert "report_export" in celery_app.tasks
    assert celery_app.conf.task_track_started is True
    assert celery_app.conf.worker_send_task_events is True
    assert celery_app.conf.worker_prefetch_multiplier == 1
