from __future__ import annotations

import unittest
from pathlib import Path

from cbio_curation_assistant.cli.result import command_result
from cbio_curation_assistant.integrations.pmc import ResolvedStudyIdentifier
from cbio_curation_assistant.publications.models import PublicationMetadata
from cbio_curation_assistant.supplements.models import SupplementaryClassification
from cbio_curation_assistant.workflows.curation_report import (
    CurationReportInputs,
    PaperSource,
)
from cbio_curation_assistant.workflows.mutation_annotation import (
    GenomeNexusAttemptArtifacts,
    GenomeNexusResult,
)


class PublicationMetadataTest(unittest.TestCase):
    def test_mapping_is_normalized_once_at_the_workflow_boundary(self) -> None:
        metadata = PublicationMetadata.from_mapping(
            {
                "study_title": "  Fixture study  ",
                "sequencing_types": ["WES", "RNA-seq"],
                "key_findings": ["Finding"],
            }
        )

        self.assertEqual(metadata.study_title, "Fixture study")
        self.assertEqual(metadata.sequencing_types, ("WES", "RNA-seq"))
        self.assertEqual(metadata.key_findings, ("Finding",))
        self.assertEqual(metadata.to_dict()["sequencing_types"], ["WES", "RNA-seq"])


class SupplementaryClassificationTest(unittest.TestCase):
    def test_load_error_remains_typed_but_legacy_json_shape_is_preserved(self) -> None:
        record = SupplementaryClassification(
            file="broken.xlsx",
            sheet="-",
            classification="NOT_LOADABLE",
            cbio_target_file=None,
            curability="NO",
            priority="N/A",
            confidence=0,
            verdict="Parse error: broken",
            load_error="broken",
        )

        self.assertEqual(record.load_error, "broken")
        self.assertEqual(record.to_dict()["cbio_target_file"], "N/A")


class WorkflowModelTest(unittest.TestCase):
    def test_report_inputs_cannot_represent_two_paper_sources(self) -> None:
        inputs = CurationReportInputs(
            paper_source=PaperSource(kind="xml", path=Path("/study/article.xml")),
            supplementary_paths=(Path("/study/table.xlsx"),),
        )

        self.assertEqual(inputs.paper_source.kind, "xml")
        self.assertEqual(inputs.supplementary_selection, "explicit")
        self.assertEqual(inputs.to_dict()["paper_pdf_path"], None)
        self.assertEqual(inputs.to_dict()["paper_xml_path"], "/study/article.xml")

    def test_command_envelope_serializes_nested_domain_models(self) -> None:
        resolved = ResolvedStudyIdentifier(
            input_identifier="123",
            identifier_type="PMID",
            normalized_identifier="123",
            pmcid="PMC456",
        )
        response = command_result(
            "resolve",
            status="success",
            result=resolved,
        )

        self.assertEqual(response.result, resolved)
        self.assertEqual(response.to_dict()["result"]["pmid"], "123")

    def test_genome_nexus_candidate_cannot_claim_promoted_outputs(self) -> None:
        attempt = GenomeNexusAttemptArtifacts(Path("/study/validation/attempt"))
        with self.assertRaisesRegex(ValueError, "cannot also contain promoted"):
            GenomeNexusResult(
                genome_build="GRCh37",
                docker_image="image",
                workspace=Path("/study/curated"),
                input_file=Path("/study/curated/minimal_mutations.maf"),
                input_records=1,
                output_records=1,
                successful_annotations=1,
                failed_annotations=0,
                annotation_status_counts={"SUCCESS": 1},
                record_count_mismatch=False,
                output_file=Path("/study/curated/data_mutations.txt"),
                attempt=attempt,
            )


if __name__ == "__main__":
    unittest.main()
