# Port interfaces (Hexagonal Architecture)
from .crawler_port import ICrawler
from .repository_port import IRepository
from .notification_port import INotificationChannel, INotificationDispatcher

__all__ = [
    'ICrawler',
    'IRepository',
    'INotificationChannel',
    'INotificationDispatcher'
]
