from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, scoped_session
from contextlib import contextmanager
import sqlite3
import logging
from datetime import datetime
import os
import json

logger = logging.getLogger(__name__)

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    username = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    cart = relationship("Cart", back_populates="user")
    orders = relationship("Order", back_populates="user")

class Category(Base):
    __tablename__ = 'categories'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    description = Column(String)
    price = Column(Float)
    image_path = Column(String)  # Путь к изображению товара
    category_id = Column(Integer, ForeignKey('categories.id'))
    category = relationship("Category", back_populates="products")
    cart_items = relationship("CartItem", back_populates="product")
    order_items = relationship("OrderItem", back_populates="product")

class Cart(Base):
    __tablename__ = 'carts'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship("User", back_populates="cart")
    items = relationship("CartItem", back_populates="cart")

class CartItem(Base):
    __tablename__ = 'cart_items'
    id = Column(Integer, primary_key=True)
    cart_id = Column(Integer, ForeignKey('carts.id'))
    product_id = Column(Integer, ForeignKey('products.id'))
    quantity = Column(Integer)
    cart = relationship("Cart", back_populates="items")
    product = relationship("Product", back_populates="cart_items")

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.now)
    user = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = 'order_items'
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id'))
    product_id = Column(Integer, ForeignKey('products.id'))
    quantity = Column(Integer)
    price = Column(Float)
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")

# Инициализация базы данных
engine = create_engine('sqlite:///shop.db')
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

@contextmanager
def session_scope():
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def init_db():
    """Инициализация базы данных"""
    Base.metadata.create_all(engine)
    with session_scope() as session:
        # Создаем предустановленные категории
        categories = [
            "💨 Жижа",
            "🚬 Одноразки",
            "🔋 Под системы",
            "🍫 Снюс",
            "🛠 Аксессуары"
        ]
        
        for category_name in categories:
            if not session.query(Category).filter_by(name=category_name).first():
                category = Category(name=category_name)
                session.add(category)
        
        # Создаем тестового администратора
        admin_id = int(os.getenv('ADMIN_IDS', '0').split(',')[0])
        if admin_id:
            admin = session.query(User).filter_by(telegram_id=admin_id).first()
            if not admin:
                admin = User(telegram_id=admin_id, is_admin=True)
                session.add(admin)
        
        session.commit()
        
        # Импортируем товары из последнего бэкапа
        import_products()

# Функции для работы с пользователями
def add_user(telegram_id: int, is_admin: bool = False, username: str = None):
    """Добавление нового пользователя"""
    with session_scope() as session:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            user = User(telegram_id=telegram_id, is_admin=is_admin, username=username)
            session.add(user)
            logger.info(f"Added new user: {telegram_id}, admin: {is_admin}, username: {username}")
        else:
            user.is_admin = is_admin
            if username:
                user.username = username
            logger.info(f"Updated existing user: {telegram_id}, admin: {is_admin}, username: {username}")

def is_admin(telegram_id):
    """Проверка, является ли пользователь администратором"""
    with session_scope() as session:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        is_admin_status = user.is_admin if user else False
        logger.info(f"Checking admin status for user {telegram_id}: {is_admin_status}")
        return is_admin_status

# Функции для работы с категориями
def get_categories():
    with session_scope() as session:
        categories = session.query(Category).all()
        return [cat.name for cat in categories]

# Функции для работы с продуктами
def get_products(category=None):
    """Получение списка товаров"""
    with session_scope() as session:
        query = session.query(Product)
        if category:
            query = query.join(Category).filter(Category.name == category)
        products = query.all()
        # Преобразуем объекты SQLAlchemy в словари
        return [
            {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': product.price,
                'category': product.category.name if product.category else None,
                'image_path': product.image_path
            }
            for product in products
        ]

def add_product(name, description, price, category_name, image_path):
    with session_scope() as session:
        category = session.query(Category).filter_by(name=category_name).first()
        if category:
            product = Product(
                name=name,
                description=description,
                price=price,
                category_id=category.id,
                image_path=image_path
            )
            session.add(product)

def get_product_by_id(product_id):
    """Получение информации о товаре по его ID"""
    with session_scope() as session:
        product = session.query(Product).filter_by(id=product_id).first()
        if product:
            return {
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': product.price,
                'category': product.category.name,
                'image_path': product.image_path
            }
        return None

def add_to_cart_db(user_id, product_id):
    """Добавление товара в корзину пользователя"""
    with session_scope() as session:
        try:
            # Получаем пользователя
            user = session.query(User).filter_by(telegram_id=user_id).first()
            if not user:
                user = User(telegram_id=user_id)
                session.add(user)
                session.flush()
            
            # Получаем или создаем корзину
            cart = session.query(Cart).filter_by(user_id=user.id).first()
            if not cart:
                cart = Cart(user_id=user.id)
                session.add(cart)
                session.flush()
            
            # Получаем товар
            product = session.query(Product).filter_by(id=product_id).first()
            if not product:
                raise ValueError(f"Товар с ID {product_id} не найден")
            
            # Проверяем наличие товара в корзине
            cart_item = session.query(CartItem).filter_by(
                cart_id=cart.id,
                product_id=product_id
            ).first()
            
            if cart_item:
                cart_item.quantity += 1
            else:
                cart_item = CartItem(
                    cart_id=cart.id,
                    product_id=product_id,
                    quantity=1
                )
                session.add(cart_item)
            
            session.commit()
        except Exception as e:
            session.rollback()
            raise e 

def get_cart_items(user_id):
    """Получение товаров из корзины пользователя"""
    with session_scope() as session:
        user = session.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            return []
        
        cart = session.query(Cart).filter_by(user_id=user.id).first()
        if not cart:
            return []
        
        items = session.query(CartItem).filter_by(cart_id=cart.id).all()
        return [
            {
                'id': item.id,
                'product_id': item.product_id,
                'quantity': item.quantity,
                'name': item.product.name,
                'price': item.product.price
            }
            for item in items
        ]

def clear_cart(user_id):
    """Очистка корзины пользователя"""
    with session_scope() as session:
        user = session.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            return False
        
        cart = session.query(Cart).filter_by(user_id=user.id).first()
        if not cart:
            return False
        
        session.query(CartItem).filter_by(cart_id=cart.id).delete()
        return True

def create_order(user_id):
    """Создание заказа из корзины"""
    with session_scope() as session:
        user = session.query(User).filter_by(telegram_id=user_id).first()
        if not user:
            return None
        
        cart = session.query(Cart).filter_by(user_id=user.id).first()
        if not cart:
            return None
        
        items = session.query(CartItem).filter_by(cart_id=cart.id).all()
        if not items:
            return None
        
        order = Order(user_id=user.id)
        session.add(order)
        session.flush()
        
        for item in items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price=item.product.price
            )
            session.add(order_item)
        
        session.query(CartItem).filter_by(cart_id=cart.id).delete()
        return order.id

def get_order_details(order_id):
    """Получение деталей заказа"""
    with session_scope() as session:
        order = session.query(Order).filter_by(id=order_id).first()
        if not order:
            return None
        
        items = session.query(OrderItem).filter_by(order_id=order_id).all()
        return {
            'order_id': order.id,
            'user_id': order.user.telegram_id,
            'username': f"@{order.user.username}" if order.user.username else "Не указан",
            'items': [
                {
                    'name': item.product.name,
                    'quantity': item.quantity,
                    'price': item.price
                }
                for item in items
            ],
            'total': sum(item.price * item.quantity for item in items)
        } 

def export_products():
    """Экспорт всех товаров в JSON файл"""
    try:
        with session_scope() as session:
            products = session.query(Product).all()
            products_data = []
            
            for product in products:
                product_data = {
                    'name': product.name,
                    'description': product.description,
                    'price': product.price,
                    'category': product.category.name,
                    'image_path': product.image_path
                }
                products_data.append(product_data)
            
            # Создаем директорию для бэкапов, если её нет
            if not os.path.exists('backups'):
                os.makedirs('backups')
            
            # Создаем имя файла с текущей датой
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f'backups/products_{timestamp}.json'
            
            # Сохраняем данные в JSON файл
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(products_data, f, ensure_ascii=False, indent=4)
            
            logger.info(f"Exported {len(products_data)} products to {backup_file}")
            return backup_file
    except Exception as e:
        logger.error(f"Error exporting products: {e}")
        return None

def import_products(backup_file=None):
    """Импорт товаров из JSON файла"""
    try:
        # Если файл не указан, используем последний бэкап
        if not backup_file:
            if not os.path.exists('backups'):
                logger.error("No backup directory found")
                return False
            
            backup_files = [f for f in os.listdir('backups') if f.startswith('products_') and f.endswith('.json')]
            if not backup_files:
                logger.error("No backup files found")
                return False
            
            backup_file = os.path.join('backups', max(backup_files))
        
        # Читаем данные из JSON файла
        with open(backup_file, 'r', encoding='utf-8') as f:
            products_data = json.load(f)
        
        with session_scope() as session:
            for product_data in products_data:
                # Получаем категорию
                category = session.query(Category).filter_by(name=product_data['category']).first()
                if not category:
                    logger.warning(f"Category {product_data['category']} not found, skipping product {product_data['name']}")
                    continue
                
                # Проверяем, существует ли уже такой товар
                existing_product = session.query(Product).filter_by(
                    name=product_data['name'],
                    category_id=category.id
                ).first()
                
                if not existing_product:
                    # Создаем новый товар
                    product = Product(
                        name=product_data['name'],
                        description=product_data['description'],
                        price=product_data['price'],
                        category_id=category.id,
                        image_path=product_data['image_path']
                    )
                    session.add(product)
            
            session.commit()
            logger.info(f"Imported {len(products_data)} products from {backup_file}")
            return True
    except Exception as e:
        logger.error(f"Error importing products: {e}")
        return False 
