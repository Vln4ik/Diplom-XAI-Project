def test_celery_registers_project_tasks():
    from app.workers.celery_app import celery_app

    assert "document_process" in celery_app.tasks
    assert "report_analyze" in celery_app.tasks
    assert "report_generate" in celery_app.tasks
    assert "report_export" in celery_app.tasks
