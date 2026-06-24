from django.urls import path
from django.contrib.auth import views as auth_views
from . import public_views as views

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("products/", views.products, name="products"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path('delivery-charge-api/', views.website_delivery_charge_api, name='website_delivery_charge_api'),

    # SEO & Crawlers
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('sitemap.xml', views.sitemap_xml, name='sitemap_xml'),

    path("contact/", views.contact, name="contact"),
    path("blog/", views.blog, name="blog_list"),
    path("blog/<slug:slug>/", views.blog_detail, name="blog_detail"),
    
    # Cart
    path("cart/", views.cart_view, name="cart"),
    path("cart/add/<int:pk>/", views.add_to_cart, name="add_to_cart"),
    path("cart/update/", views.update_cart, name="update_cart"),
    path("cart/remove/<str:pk>/", views.remove_from_cart, name="remove_from_cart"),

    # Checkout
    path("checkout/", views.checkout, name="checkout"),
    path("order-success/", views.order_success, name="order_success"),
    path("order-success/<str:order_number>/", views.order_success, name="order_success"),

    # Policy Pages
    path("privacy-policy/", views.privacy_policy, name="privacy_policy"),
    path("terms-and-conditions/", views.terms_conditions, name="terms_conditions"),
    path("delivery-charges/", views.delivery_charges, name="delivery_charges"),

    # Authentication
    path("login/", views.login_view, name="public_login"),
    path("register/", views.register_view, name="public_register"),
    path("logout/", views.logout_view, name="public_logout"),
    path("my-account/", views.my_account, name="public_my_account"),

    # Password Reset
    path("password-reset/", auth_views.PasswordResetView.as_view(
        template_name="public/password_reset.html", 
        email_template_name="emails/password_reset_email.html", 
        subject_template_name="emails/password_reset_subject.txt", 
        success_url="/public/password-reset/done/"
    ), name="password_reset"),
    path("password-reset/done/", auth_views.PasswordResetDoneView.as_view(
        template_name="public/password_reset_done.html"
    ), name="password_reset_done"),
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="public/password_reset_confirm.html", 
        success_url="/public/reset/done/"
    ), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="public/password_reset_complete.html"
    ), name="password_reset_complete"),

    # API
    path("api/delivery-charge/", views.website_delivery_charge_api, name="website_delivery_charge_api"),

    # Custom Pages (Catch-all must be at the bottom)
    path('<slug:slug>/', views.custom_page_detail, name='custom_page_detail'),
]
