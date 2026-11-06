"""Small document factories for API tests."""

from __future__ import annotations

from app.core.permissions import ROLE_PERMISSIONS
from app.core.security import hash_password
from app.modules.identity.models import Role, User
from app.modules.organization.models import Company

DEV_PASSWORD = "ChangeMe123!"


async def make_company(name: str, slug: str) -> Company:
    company = Company(name=name, slug=slug)
    await company.insert()
    return company


async def make_user(
    *,
    email: str,
    company: Company,
    role_name: str,
    password: str = DEV_PASSWORD,
) -> User:
    role = await Role.find_one(Role.company_id == str(company.id), Role.name == role_name)
    if role is None:
        role = Role(
            company_id=str(company.id),
            name=role_name,
            permission_keys=sorted(ROLE_PERMISSIONS[role_name]),
        )
        await role.insert()
    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        company_id=str(company.id),
        role_ids=[str(role.id)],
    )
    await user.insert()
    return user
