
from lib.modules.crypto import CryptoOperationModule, ModuleDependency

from .fake_db import fake_session


crypto_with_fake_session = CryptoOperationModule(ModuleDependency(session=fake_session))