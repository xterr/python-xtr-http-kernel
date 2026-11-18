from __future__ import annotations

from xtr_http_kernel.data_collector import DataCollectorTemplates


def test_a_collectors_template_is_found_by_name() -> None:
    templates = DataCollectorTemplates(
        (("request", "@a/request.html.j2"), ("time", "@a/t.html.j2"))
    )

    assert templates.template_of("time") == "@a/t.html.j2"
    assert templates.template_of("router") is None


def test_no_collector_means_no_template() -> None:
    assert DataCollectorTemplates().entries == ()
