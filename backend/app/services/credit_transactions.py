from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credit_ledger import CreditLedger
from app.models.generation_tasks import GenerationTask
from app.models.users import User


def _billing_key(task: GenerationTask) -> str:
    if task.retry_count == 0:
        return task.idempotency_key
    return retry_billing_key(task.id, task.retry_count)


def retry_billing_key(task_id, retry_count: int) -> str:
    return f"task:{task_id}:retry:{retry_count}"


async def release_reserved_credits(
    session: AsyncSession,
    task: GenerationTask,
    *,
    amount: int | None = None,
) -> None:
    release_amount = task.estimated_credits if amount is None else amount
    if release_amount <= 0:
        return
    billing_key = _billing_key(task)
    existing = await session.scalar(
        select(CreditLedger).where(
            CreditLedger.user_id == task.user_id,
            CreditLedger.idempotency_key == billing_key,
            CreditLedger.entry_type == "generation_release",
        )
    )
    if existing is not None:
        return
    user = await session.get(User, task.user_id, with_for_update=True)
    reserve = await session.scalar(
        select(CreditLedger).where(
            CreditLedger.user_id == task.user_id,
            CreditLedger.idempotency_key == billing_key,
            CreditLedger.entry_type == "generation_reserve",
        )
    )
    user.credit_balance += release_amount
    session.add(
        CreditLedger(
            user_id=task.user_id,
            task_id=task.id,
            entry_type="generation_release",
            amount=release_amount,
            balance_after=user.credit_balance,
            related_entry_id=reserve.id if reserve is not None else None,
            idempotency_key=billing_key,
            description=None,
        )
    )


async def finalize_reserved_credits(
    session: AsyncSession, task: GenerationTask
) -> None:
    billing_key = _billing_key(task)
    existing = await session.scalar(
        select(CreditLedger).where(
            CreditLedger.user_id == task.user_id,
            CreditLedger.idempotency_key == billing_key,
            CreditLedger.entry_type == "generation_finalize",
        )
    )
    if existing is not None:
        return
    user = await session.get(User, task.user_id, with_for_update=True)
    reserve = await session.scalar(
        select(CreditLedger).where(
            CreditLedger.user_id == task.user_id,
            CreditLedger.idempotency_key == billing_key,
            CreditLedger.entry_type == "generation_reserve",
        )
    )
    session.add(
        CreditLedger(
            user_id=task.user_id,
            task_id=task.id,
            entry_type="generation_finalize",
            amount=0,
            balance_after=user.credit_balance,
            related_entry_id=reserve.id if reserve is not None else None,
            idempotency_key=billing_key,
            description=None,
        )
    )
