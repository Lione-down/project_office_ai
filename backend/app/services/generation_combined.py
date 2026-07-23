from app.services.generation_worker import StepExecutionResult


class CombinedGenerationExecutor:
    def __init__(
        self,
        *,
        presentation_pipeline,
        spreadsheet_pipeline,
    ) -> None:
        self._pipelines = {
            "pptx": presentation_pipeline,
            "xlsx": spreadsheet_pipeline,
        }

    async def execute(self, context) -> StepExecutionResult:
        pipeline = self._pipelines.get(context.output_kind)
        if pipeline is None:
            return StepExecutionResult.permanent_failure(
                "generation_output_kind_invalid"
            )
        result = await pipeline.execute(context)
        if not isinstance(result, StepExecutionResult):
            return StepExecutionResult.permanent_failure(
                "generation_pipeline_result_invalid"
            )
        return result
