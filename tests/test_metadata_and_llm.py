from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from cbio_curation_assistant.config import LLMConfig
from cbio_curation_assistant.llm_client import (
    _should_retry_litellm_as_responses,
    call_llm_with_retry,
    parse_llm_json,
)
from cbio_curation_assistant.metadata_merge import (
    build_study_id,
    is_missing_metadata_value,
    merge_missing_metadata_fields,
)
from cbio_curation_assistant.pdf_metadata_regex import extract_metadata_regex
from cbio_curation_assistant.xml_metadata import (
    extract_metadata_from_xml,
    extract_xml_llm_text,
    extract_xml_text,
)


JATS_XML = """
<article>
  <front>
    <journal-meta>
      <journal-title-group>
        <journal-title>Journal of Characterization</journal-title>
      </journal-title-group>
    </journal-meta>
    <article-meta>
      <article-id pub-id-type="pmid">12345678</article-id>
      <article-id pub-id-type="doi">10.1000/example</article-id>
      <title-group>
        <article-title>Genomic landscape of lung adenocarcinoma</article-title>
      </title-group>
      <contrib-group>
        <contrib contrib-type="author" corresp="yes">
          <name><surname>Smith</surname><given-names>Ada</given-names></name>
          <email>ada@example.org</email>
        </contrib>
      </contrib-group>
      <pub-date><year>2024</year></pub-date>
      <abstract><p>We characterized the cohort. A second sentence follows.</p></abstract>
    </article-meta>
  </front>
  <body><sec><p>Body evidence appears here.</p></sec></body>
  <back><ref-list><ref>Unrelated cited paper.</ref></ref-list></back>
</article>
"""


class XmlMetadataTest(unittest.TestCase):
    def test_structured_jats_metadata_is_extracted_without_an_llm(self) -> None:
        metadata = extract_metadata_from_xml(JATS_XML)

        self.assertEqual(
            metadata["study_title"],
            "Genomic landscape of lung adenocarcinoma",
        )
        self.assertEqual(metadata["journal"], "Journal of Characterization")
        self.assertEqual(metadata["year"], "2024")
        self.assertEqual(metadata["pmid"], "12345678")
        self.assertEqual(metadata["doi"], "10.1000/example")
        self.assertEqual(metadata["first_author_surname"], "Smith")
        self.assertEqual(metadata["description"], "We characterized the cohort.")
        self.assertEqual(metadata["study_id_suggestion"], "study_smith_2024")
        self.assertIn("ada@example.org", metadata["corresponding_authors"])

    def test_llm_text_excludes_back_matter(self) -> None:
        text = extract_xml_llm_text(JATS_XML)

        self.assertIn("Title\nGenomic landscape", text)
        self.assertIn("Abstract\nWe characterized", text)
        self.assertIn("Body\nBody evidence", text)
        self.assertNotIn("Unrelated cited paper", text)

    def test_general_xml_text_includes_back_matter(self) -> None:
        text = extract_xml_text(JATS_XML)
        self.assertIn("Unrelated cited paper", text)


class MetadataMergeTest(unittest.TestCase):
    def test_missing_value_detection_covers_empty_collections_and_markers(self) -> None:
        for value in (None, "", "?", "Unknown", [], {}, set()):
            with self.subTest(value=value):
                self.assertTrue(is_missing_metadata_value(value))
        self.assertFalse(is_missing_metadata_value(0))
        self.assertFalse(is_missing_metadata_value("known"))

    def test_completion_only_fills_missing_fields_and_rebuilds_study_id(self) -> None:
        merged = merge_missing_metadata_fields(
            {
                "study_title": "Preserved",
                "cancer_type": None,
                "first_author_surname": "Smith",
                "year": "2024",
            },
            {
                "study_title": "Replacement",
                "cancer_type": "luad",
                "first_author_surname": "Other",
            },
        )

        self.assertEqual(merged["study_title"], "Preserved")
        self.assertEqual(merged["cancer_type"], "luad")
        self.assertEqual(merged["first_author_surname"], "Smith")
        self.assertEqual(merged["study_id_suggestion"], "luad_smith_2024")

    def test_build_study_id_sanitizes_values(self) -> None:
        self.assertEqual(build_study_id("Non Small Cell", "O'Neil", "2024"), "non_small_cell_o_neil_2024")
        self.assertEqual(build_study_id(None, "Smith", "2024"), "study_smith_2024")
        self.assertIsNone(build_study_id("luad", None, "2024"))


class PdfRegexMetadataTest(unittest.TestCase):
    def test_regex_extraction_recognizes_core_publication_and_study_fields(self) -> None:
        text = """
        Genomic characterization of lung adenocarcinoma reveals recurrent mutations
        Nature Communications
        DOI: 10.1000/example
        PMID: 12345678
        Accepted: 1 January 2024
        Smith et al.
        We collected 62 samples from 25 patients and performed WES.
        Reads were aligned to GRCh38. Data are available as GSE123456.
        """

        metadata = extract_metadata_regex(text)

        self.assertEqual(metadata["cancer_type"], "luad")
        self.assertEqual(metadata["num_samples"], "62")
        self.assertEqual(metadata["num_patients"], "25")
        self.assertEqual(metadata["reference_genome"], "hg38")
        self.assertIn("WES", metadata["sequencing_types"])
        self.assertEqual(metadata["pmid"], "12345678")
        self.assertEqual(metadata["doi"], "10.1000/example")
        self.assertEqual(metadata["first_author_surname"], "Smith")
        self.assertEqual(metadata["year"], "2024")
        self.assertIn("GSE123456", metadata["data_repositories"])


class LlmJsonParsingTest(unittest.TestCase):
    def test_parser_accepts_fences_comments_trailing_commas_and_surrounding_text(self) -> None:
        raw = """
        Here is the result:
        ```json
        {
          // a line comment
          "study": "value", /* block comment */
          "items": [1, 2,],
        }
        ```
        """
        self.assertEqual(
            parse_llm_json(raw),
            {"study": "value", "items": [1, 2]},
        )

    def test_parser_unwraps_single_object_lists_and_double_encoded_json(self) -> None:
        self.assertEqual(parse_llm_json('[{"value": 1}]'), {"value": 1})
        self.assertEqual(parse_llm_json('"{\\"value\\": 1}"'), {"value": 1})

    def test_parser_rejects_non_object_payloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "not an object"):
            parse_llm_json("[1, 2]")

    def test_provider_router_rejects_unknown_providers(self) -> None:
        config = LLMConfig(provider="Other", api_key="", model="model")
        with self.assertRaisesRegex(ValueError, "Unsupported LLM provider"):
            call_llm_with_retry(config=config, system="system", user_content="user")

    def test_openai_responses_mode_uses_the_responses_adapter(self) -> None:
        config = LLMConfig(
            provider="OpenAI",
            api_key="key",
            model="model",
            api_mode="responses",
        )
        client = Mock()
        with (
            patch(
                "cbio_curation_assistant.llm_client._build_openai_client",
                return_value=client,
            ),
            patch(
                "cbio_curation_assistant.llm_client.call_openai_responses_with_retry",
                return_value="response",
            ) as responses,
        ):
            result = call_llm_with_retry(
                config=config,
                system="system",
                user_content="user",
                max_tokens=12,
            )

        self.assertEqual(result, "response")
        responses.assert_called_once_with(
            client=client,
            model="model",
            system="system",
            user_content="user",
            max_tokens=12,
        )

    def test_litellm_404_fallback_requires_proxy_chat_mode(self) -> None:
        class StatusError(Exception):
            status_code = 404

        exception = StatusError("not found")
        eligible = LLMConfig(
            provider="LiteLLM",
            api_key="key",
            model="model",
            base_url="https://proxy.example",
            api_mode="chat_completions",
        )
        ineligible = LLMConfig(
            provider="LiteLLM",
            api_key="key",
            model="model",
            base_url="",
            api_mode="chat_completions",
        )

        self.assertTrue(_should_retry_litellm_as_responses(eligible, exception))
        self.assertFalse(_should_retry_litellm_as_responses(ineligible, exception))


if __name__ == "__main__":
    unittest.main()
