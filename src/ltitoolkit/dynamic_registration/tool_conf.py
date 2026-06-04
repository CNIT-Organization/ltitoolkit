"""Bridge dynamically-registered platforms into the launch machinery.

``StoredToolConf`` is a :class:`ToolConfAbstract` backed by a
:class:`RegistrationStore`, so the same OIDC login / message launch flow that
works with a static ``ToolConfDict`` also works for platforms that registered
themselves via Dynamic Registration. The tool's own key pair is supplied once
and attached to every resolved registration (used to sign client assertions).
"""

from __future__ import annotations

from ..core.deployment import Deployment
from ..core.exception import LtiException
from ..core.registration import Registration
from ..core.tool_config.abstract import ToolConfAbstract
from .models import ToolRegistration
from .store import RegistrationStore


class StoredToolConf(ToolConfAbstract):
    """Tool configuration resolved from a registration store at runtime."""

    def __init__(
        self,
        store: RegistrationStore,
        *,
        private_key: str,
        public_key: str | None = None,
    ) -> None:
        super().__init__()
        self._store = store
        self._private_key = private_key
        self._public_key = public_key

    # Dynamic registration always works in the (recommended) many-clients model:
    # an issuer may have multiple client_ids, and we always know the client_id.
    def check_iss_has_one_client(self, iss: str) -> bool:
        return False

    def check_iss_has_many_clients(self, iss: str) -> bool:
        return True

    # -- registration resolution ------------------------------------------

    def _build_registration(self, record: ToolRegistration) -> Registration:
        registration = (
            Registration()
            .set_issuer(record.issuer)
            .set_client_id(record.client_id)
            .set_auth_login_url(record.auth_login_url)
            .set_auth_token_url(record.auth_token_url)
            .set_key_set_url(record.key_set_url)
            .set_tool_private_key(self._private_key)
        )
        if record.auth_audience:
            registration.set_auth_audience(record.auth_audience)
        if self._public_key:
            registration.set_tool_public_key(self._public_key)
        return registration

    def _lookup(self, iss: str, client_id: str | None) -> ToolRegistration:
        record = None
        if client_id:
            record = self._store.get(iss, client_id)
        else:
            candidates = self._store.find_by_issuer(iss)
            record = candidates[0] if candidates else None
        if record is None:
            raise LtiException(
                f"No registration found for issuer={iss} client_id={client_id}"
            )
        return record

    def find_registration_by_issuer(self, iss, *args, **kwargs) -> Registration:
        return self._build_registration(self._lookup(iss, None))

    def find_registration_by_params(self, iss, client_id, *args, **kwargs) -> Registration:
        return self._build_registration(self._lookup(iss, client_id))

    # -- deployment resolution --------------------------------------------

    def _deployment(self, record: ToolRegistration, deployment_id: str):
        # If the registration captured specific deployment_ids, enforce them;
        # otherwise accept the launch's deployment_id (deployments are often
        # created separately from registration, e.g. on Canvas).
        if record.deployment_ids and deployment_id not in record.deployment_ids:
            return None
        return Deployment().set_deployment_id(deployment_id)

    def find_deployment(self, iss, deployment_id):
        try:
            record = self._lookup(iss, None)
        except LtiException:
            return None
        return self._deployment(record, deployment_id)

    def find_deployment_by_params(self, iss, deployment_id, client_id, *args, **kwargs):
        try:
            record = self._lookup(iss, client_id)
        except LtiException:
            return None
        return self._deployment(record, deployment_id)
