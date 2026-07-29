from uuid import UUID


class WorkflowQueueConsumer:
    def __init__(
        self,
        queue,
        worker,
        media_worker=None,
        video_worker=None,
    ) -> None:
        self._queue = queue
        self._worker = worker
        self._media_worker = media_worker
        self._video_worker = video_worker

    async def consume_once(self):
        message = await self._queue.dequeue()
        if message is None:
            return None
        try:
            event_type = message["event_type"]
            if event_type == "brief.generate":
                task_id = UUID(str(message["payload"]["workflow_task_id"]))
                worker = self._worker
            elif event_type == "image.generate" and self._media_worker is not None:
                task_id = UUID(str(message["payload"]["media_job_id"]))
                worker = self._media_worker
            elif (
                event_type in {"video.generate", "video.poll"}
                and self._video_worker is not None
            ):
                task_id = UUID(str(message["payload"]["media_job_id"]))
                worker = self._video_worker
            else:
                raise ValueError("workflow queue event type is invalid")
        except (KeyError, TypeError, ValueError) as exception:
            raise ValueError("workflow queue message is invalid") from exception
        return await worker.process(task_id)


class RedisWorkflowQueue:
    queue_key = "office_ai:workflow:queue"

    def __init__(self, redis, *, timeout_seconds: int = 2) -> None:
        self._redis = redis
        self._timeout_seconds = timeout_seconds

    async def dequeue(self):
        return await self._redis.dequeue_generation(
            self.queue_key,
            timeout_seconds=self._timeout_seconds,
        )
