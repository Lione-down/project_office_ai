from app.services.decks.contracts import DeckBrief
from app.services.renderers.presentation.contracts import PresentationPlan


class DeckPresentationComposer:
    def compose(
        self,
        deck: DeckBrief,
        *,
        template_code: str,
        revision: int,
    ) -> PresentationPlan:
        evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for slide in deck.slides
                for provenance in slide.provenance
                for evidence_id in provenance.evidence_ids
            )
        )
        slides = [
            self._slide(deck, index, len(deck.slides))
            for index in range(len(deck.slides))
        ]
        return PresentationPlan.validate_for_renderer(
            {
                "schema_version": "presentation-plan.v1",
                "renderer_version": "ppt-renderer.v1",
                "template": {"code": template_code, "version": "1.0.0"},
                "locale": deck.language,
                "metadata": {
                    "title": deck.topic[:500],
                    "subject": f"{deck.audience}｜{deck.style}"[:500],
                    "author": "Office AI",
                    "company": "Office AI",
                    "revision": str(revision),
                },
                "evidence_ids": evidence_ids,
                "images": {},
                "data_sources": {},
                "slides": slides,
            }
        )

    @staticmethod
    def _slide(deck: DeckBrief, index: int, slide_count: int) -> dict:
        slide = deck.slides[index]
        evidence_ids = list(
            dict.fromkeys(
                evidence_id
                for provenance in slide.provenance
                for evidence_id in provenance.evidence_ids
            )
        )
        notes = DeckPresentationComposer._notes(slide.speaker_notes)
        provenance_kinds = {item.kind for item in slide.provenance}
        if "agnes_inference" in provenance_kinds:
            notes.append("本页含 AI 生成且尚未核验的内容。")
        if evidence_ids:
            notes.append("Evidence: " + ", ".join(evidence_ids))
        layout = (
            "title"
            if index == 0
            else "closing"
            if index == slide_count - 1
            else "content"
        )
        elements = []
        for body_index, body in enumerate(slide.body):
            element = {
                "type": "text",
                "text": body,
                "x": 0.9,
                "y": 1.35 + 0.43 * body_index,
                "w": 11.5,
                "h": 0.35,
            }
            if evidence_ids:
                element["evidence_ids"] = evidence_ids
            elements.append(element)
        return {
            "layout": layout,
            "title": slide.title,
            "subtitle": slide.purpose if index == 0 else None,
            "speaker_notes": notes or ["用户已确认的 Deck Brief 页面。"],
            "elements": elements,
        }

    @staticmethod
    def _notes(value: str) -> list[str]:
        cleaned = value.strip()
        return [
            cleaned[offset : offset + 500] for offset in range(0, len(cleaned), 500)
        ][:18]
