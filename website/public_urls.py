from django.urls import path
from . import public_views as views

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("products/", views.products, name="products"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path("contact/", views.contact, name="contact"),
    path("pages/<slug:slug>/", views.custom_page_detail, name="custom_page_detail"),
    path("blog/", views.blog, name="blog_list"),
    path("blog/<slug:slug>/", views.blog_detail, name="blog_detail"),
    
    # Cart
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<int:pk>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/", views.update_cart, name="update_cart"),
    path("cart/remove/<int:pk>/", views.remove_from_cart, name="remove_from_cart"),

    # Checkout
    path("checkout/", views.checkout, name="checkout"),
    path("order-success/", views.order_success, name="order_success"),
    path("order-success/<str:order_number>/", views.order_success, name="order_success"),

    # Policy Pages
    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),
    path("terms-and-conditions/", views.terms_conditions, name="terms_conditions"),
    path("delivery-charges/", views.delivery_charges, name="delivery_charges"),

    # API
    path("api/delivery-charge/", views.website_delivery_charge_api, name="website_delivery_charge_api"),
]
