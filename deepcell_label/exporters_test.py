"""Tests for exporters.py"""

import io

from deepcell_label import exporters, models
from deepcell_label.conftest import DummyLoader


class TestExporter:
    def test_export_npz(self, app, db_session):
        with app.app_context():
            db_session.autoflush = False
            project = models.Project.create(DummyLoader())
            exporter = exporters.Exporter(project, 'npz')
            file_ = exporter.export()
            assert isinstance(file_, io.BytesIO)

    def test_export_trk(self, app, db_session):
        with app.app_context():
            db_session.autoflush = False
            project = models.Project.create(DummyLoader())
            exporter = exporters.Exporter(project, 'trk')
            file_ = exporter.export()
            assert isinstance(file_, io.BytesIO)


class TestS3Exporter:
    def test_export(self, mocker, app, db_session):
        with app.app_context():
            mocked = mocker.patch('boto3.s3.inject.upload_fileobj')
            db_session.autoflush = False
            project = models.Project.create(DummyLoader())
            exporter = exporters.S3Exporter(project, 'npz')
            exporter.export('test')
            mocked.assert_called()
