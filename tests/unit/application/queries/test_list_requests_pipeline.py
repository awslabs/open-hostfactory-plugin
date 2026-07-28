"""Unit tests for ListRequestsHandler pipeline branches.

Exercises the filter/search/sort/pagination pipeline of
application/queries/request_query_handlers.py::ListRequestsHandler that the
existing request-type tests do not reach: provider/status/template filters,
free-text ``q`` search, sort ordering, offset/limit slicing, limit clamping,
and DTO-level ``filter_expressions``.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from orb.application.request.queries import ListRequestsQuery


def _make_request(
    request_id="req-1",
    template_id="tmpl-1",
    provider_name="aws",
    provider_type="aws",
    provider_api="RunInstances",
    status_value="pending",
    machine_ids=None,
):
    return SimpleNamespace(
        request_id=SimpleNamespace(value=request_id),
        request_type=None,
        template_id=template_id,
        provider_api=provider_api,
        provider_name=provider_name,
        provider_type=provider_type,
        status=SimpleNamespace(value=status_value),
        machine_ids=machine_ids or [],
    )


def _run(all_requests, query, filter_side_effect=None):
    from orb.application.queries.request_query_handlers import ListRequestsHandler

    mock_filter_service = MagicMock()
    mock_filter_service.apply_filters.side_effect = filter_side_effect or (lambda items, _: items)

    mock_uow = MagicMock()
    mock_uow.requests.find_all.return_value = all_requests
    mock_uow.machines.find_by_ids.return_value = []
    mock_uow.__enter__ = lambda s: s
    mock_uow.__exit__ = MagicMock(return_value=False)

    mock_uow_factory = MagicMock()
    mock_uow_factory.create_unit_of_work.return_value = mock_uow

    with patch("orb.application.queries.request_query_handlers.RequestDTOFactory") as MockFactory:
        mock_dto_factory = MagicMock()
        MockFactory.return_value = mock_dto_factory
        mock_dto_factory.create_from_domain.side_effect = lambda req, machines: SimpleNamespace(
            request_id=str(req.request_id.value),
            template_id=req.template_id,
        )

        handler = ListRequestsHandler(
            uow_factory=mock_uow_factory,
            logger=MagicMock(),
            error_handler=MagicMock(),
            generic_filter_service=mock_filter_service,
        )
        return asyncio.run(handler.execute_query(query))


class TestListRequestsPipeline:
    def test_filter_by_provider_name(self):
        reqs = [
            _make_request("r1", provider_name="aws"),
            _make_request("r2", provider_name="gcp"),
        ]
        result = _run(reqs, ListRequestsQuery(provider_name="aws"))
        assert result.total_count == 1
        assert result.total_unfiltered == 2
        assert result.items[0].request_id == "r1"

    def test_filter_by_provider_type(self):
        reqs = [
            _make_request("r1", provider_type="aws"),
            _make_request("r2", provider_type="k8s"),
        ]
        result = _run(reqs, ListRequestsQuery(provider_type="k8s"))
        assert result.total_count == 1
        assert result.items[0].request_id == "r2"

    def test_filter_by_status(self):
        from orb.domain.request.value_objects import RequestStatus

        reqs = [
            _make_request("r1", status_value=RequestStatus.PENDING.value),
            _make_request("r2", status_value=RequestStatus.COMPLETED.value),
        ]
        # RequestStatus comparison — set request.status to the enum for equality.
        reqs[0].status = RequestStatus.PENDING
        reqs[1].status = RequestStatus.COMPLETED
        result = _run(reqs, ListRequestsQuery(status=RequestStatus.PENDING.value))
        assert result.total_count == 1
        assert result.items[0].request_id == "r1"

    def test_filter_by_template_id(self):
        reqs = [
            _make_request("r1", template_id="tmpl-a"),
            _make_request("r2", template_id="tmpl-b"),
        ]
        result = _run(reqs, ListRequestsQuery(template_id="tmpl-b"))
        assert result.total_count == 1
        assert result.items[0].request_id == "r2"

    def test_free_text_search_matches_template(self):
        reqs = [
            _make_request("r1", template_id="web-server"),
            _make_request("r2", template_id="db-server"),
        ]
        result = _run(reqs, ListRequestsQuery(q="web"))
        assert result.total_count == 1
        assert result.items[0].request_id == "r1"

    def test_sort_descending_by_template(self):
        reqs = [
            _make_request("r1", template_id="aaa"),
            _make_request("r2", template_id="zzz"),
        ]
        result = _run(reqs, ListRequestsQuery(sort="-template_id"))
        assert [i.request_id for i in result.items] == ["r2", "r1"]

    def test_sort_ascending_by_template(self):
        reqs = [
            _make_request("r1", template_id="zzz"),
            _make_request("r2", template_id="aaa"),
        ]
        result = _run(reqs, ListRequestsQuery(sort="+template_id"))
        assert [i.request_id for i in result.items] == ["r2", "r1"]

    def test_offset_and_limit_slicing(self):
        reqs = [_make_request(f"r{i}", template_id=f"t{i:02d}") for i in range(5)]
        result = _run(reqs, ListRequestsQuery(sort="+template_id", offset=1, limit=2))
        assert result.total_count == 5
        assert [i.request_id for i in result.items] == ["r1", "r2"]

    def test_zero_limit_returns_no_items_but_counts(self):
        reqs = [_make_request(f"r{i}") for i in range(3)]
        result = _run(reqs, ListRequestsQuery(limit=0))
        assert result.total_count == 3
        assert result.items == []

    def test_limit_clamped_to_1000(self):
        reqs = [_make_request(f"r{i}", template_id=f"t{i:04d}") for i in range(3)]
        result = _run(reqs, ListRequestsQuery(limit=5000))
        # No error; all 3 returned (fewer than the clamp).
        assert result.total_count == 3
        assert len(result.items) == 3

    def test_filter_expressions_applied_on_dtos(self):
        from orb.application.queries.request_query_handlers import ListRequestsHandler

        class _DTO:
            def __init__(self, request_id, template_id):
                self.request_id = request_id
                self.template_id = template_id

            def model_dump(self):
                return {"request_id": self.request_id, "template_id": self.template_id}

        reqs = [
            _make_request("r1", template_id="keep"),
            _make_request("r2", template_id="drop"),
        ]

        mock_filter_service = MagicMock()
        mock_filter_service.apply_filters.side_effect = lambda dicts, _: [
            d for d in dicts if d["template_id"] == "keep"
        ]

        mock_uow = MagicMock()
        mock_uow.requests.find_all.return_value = reqs
        mock_uow.machines.find_by_ids.return_value = []
        mock_uow.__enter__ = lambda s: s
        mock_uow.__exit__ = MagicMock(return_value=False)
        mock_uow_factory = MagicMock()
        mock_uow_factory.create_unit_of_work.return_value = mock_uow

        with (
            patch(
                "orb.application.queries.request_query_handlers.RequestDTOFactory"
            ) as MockFactory,
            patch("orb.application.queries.request_query_handlers.RequestDTO") as MockDTO,
        ):
            MockFactory.return_value.create_from_domain.side_effect = lambda req, machines: _DTO(
                str(req.request_id.value), req.template_id
            )
            MockDTO.model_validate.side_effect = lambda d: _DTO(d["request_id"], d["template_id"])
            handler = ListRequestsHandler(
                uow_factory=mock_uow_factory,
                logger=MagicMock(),
                error_handler=MagicMock(),
                generic_filter_service=mock_filter_service,
            )
            result = asyncio.run(
                handler.execute_query(ListRequestsQuery(filter_expressions=["template_id==keep"]))
            )

        assert result.total_count == 2
        assert len(result.items) == 1
        assert result.items[0].template_id == "keep"
