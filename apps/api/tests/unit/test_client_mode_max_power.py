"""Tests unitaires pour la gestion de la puissance maximale quotidienne (DCMP / Pmax) en mode client."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.client_mode import MaxPowerData
from src.services.local_data import format_max_power_response
from src.services.sync import SyncService
from src.services.statistics import StatisticsService
from src.services.exporters.home_assistant import HomeAssistantExporter

PRM = "99999999999991"


def envelope(data):
    return {"success": True, "data": data}


def make_sync_service() -> SyncService:
    service = SyncService.__new__(SyncService)
    service.db = MagicMock()
    return service


class TestParseMaxPowerReading:
    def test_puissance_max_2026(self, enedis_fixture):
        service = make_sync_service()
        fixture = enedis_fixture("mesure_puissance_conso_max_quotidienne")
        records = service._parse_max_power_reading(envelope(fixture), PRM)

        assert len(records) == 2
        assert records[0]["usage_point_id"] == PRM
        assert records[0]["date"] == date(2026, 9, 29)
        assert records[0]["value"] == 4680
        assert records[0]["event_time"] == "13:03:35"
        assert records[0]["source"] == "myelectricaldata"

        assert records[1]["date"] == date(2026, 9, 30)
        assert records[1]["value"] == 6510
        assert records[1]["event_time"] == "12:50:25"

    def test_format_max_power_response(self):
        readings = [
            {"v": "4680", "d": "2026-09-29 13:03:35"},
            {"v": "6510", "d": "2026-09-30 12:50:25"},
        ]
        response = format_max_power_response(
            usage_point_id=PRM,
            start="2026-09-29",
            end="2026-10-01",
            readings=readings,
            from_cache=True,
        )

        assert response["idPrm"] == PRM
        assert response["_from_local_cache"] is True
        grandeur = response["grandeur"][0]
        assert grandeur["grandeurMetier"] == "CONS"
        assert grandeur["grandeurPhysique"] == "PMA"
        assert grandeur["unite"] == "VA"
        assert len(grandeur["points"]) == 2
        assert grandeur["points"][0]["v"] == "4680"


class TestStatisticsMaxPower:
    @pytest.mark.asyncio
    async def test_get_max_power_day_from_db(self):
        db = AsyncMock()
        stats = StatisticsService(db)

        # Simuler un résultat trouvé dans MaxPowerData
        mock_result = MagicMock()
        mock_result.first.return_value = (5820, "19:42:00")
        db.execute.return_value = mock_result

        kva, event_time = await stats.get_max_power_day(PRM, date(2026, 10, 1), "consumption")
        assert kva == 5.82
        assert event_time == "19:42:00"

    @pytest.mark.asyncio
    async def test_get_max_power_history(self):
        db = AsyncMock()
        stats = StatisticsService(db)

        row1 = MagicMock()
        row1.date = date(2026, 9, 29)
        row1.value = 4680
        row1.event_time = "13:03:35"

        row2 = MagicMock()
        row2.date = date(2026, 9, 30)
        row2.value = 6510
        row2.event_time = "12:50:25"

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [row1, row2]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        db.execute.return_value = mock_result

        history = await stats.get_max_power_history(PRM, date(2026, 9, 29), date(2026, 9, 30))
        assert len(history) == 2
        assert history[date(2026, 9, 29)]["va"] == 4680
        assert history[date(2026, 9, 29)]["kva"] == 4.68
        assert history[date(2026, 9, 29)]["time"] == "13:03:35"
        assert history[date(2026, 9, 30)]["va"] == 6510
        assert history[date(2026, 9, 30)]["kva"] == 6.51


class TestHomeAssistantMaxPowerSensor:
    @pytest.mark.asyncio
    async def test_export_max_power_sensor_publishes_mqtt(self):
        client = AsyncMock()
        stats = AsyncMock()
        db = AsyncMock()

        # Subscribed power = 6 kVA
        pdl_result = MagicMock()
        pdl_result.scalar_one_or_none.return_value = 6
        db.execute.return_value = pdl_result

        yesterday = date.today() - timedelta_days(1)
        stats.get_max_power_history.return_value = {
            yesterday: {"va": 6510, "kva": 6.51, "time": "12:50:25"}
        }

        exporter = HomeAssistantExporter(
            config={"mqtt_enabled": True, "mqtt_broker": "localhost", "prefix": "myelectricaldata"}
        )

        with patch.object(exporter, "_publish_sensor_old_format", new_callable=AsyncMock) as mock_pub_sensor, \
             patch.object(exporter, "_publish_binary_sensor", new_callable=AsyncMock) as mock_pub_binary:

            count = await exporter._export_max_power_sensor(client, stats, db, PRM)

            assert count == 2  # 1 sensor + 1 binary sensor
            mock_pub_sensor.assert_called_once()
            call_kwargs = mock_pub_sensor.call_args.kwargs
            assert call_kwargs["name"] == "max power"
            assert call_kwargs["state"] == 6510
            assert call_kwargs["unit"] == "VA"
            assert call_kwargs["device_class"] == "apparent_power"
            assert call_kwargs["attributes"]["is_over_subscribed"] is True
            assert call_kwargs["attributes"]["value_kva"] == 6.51

            # Vérifier le capteur binaire d'alerte de dépassement
            mock_pub_binary.assert_called_once()
            bin_call_kwargs = mock_pub_binary.call_args.kwargs
            assert bin_call_kwargs["name"] == "max power over subscribed"
            assert bin_call_kwargs["is_on"] is True
            assert bin_call_kwargs["device_class"] == "problem"


def timedelta_days(n: int):
    from datetime import timedelta
    return timedelta(days=n)
