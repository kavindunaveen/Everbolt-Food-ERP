import time
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q
import uuid

from .models import (
    WebsiteSettings, WebsiteCategory, WebsiteProduct,
    WebsitePage, WebsiteEnquiry, WebsiteOrder, WebsiteOrderItem, WebsiteHeroSlide
)

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def privacy_policy(request):
    return render(request, "public/privacy-policy.html")

def terms_conditions(request):
    return render(request, "public/terms-conditions.html")

def delivery_charges(request):
    return render(request, "public/delivery-charges.html")

def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")

# ============================================================
# HOME VIEW
# ============================================================

def home(request):
    settings_data = WebsiteSettings.get_settings()
    categories = WebsiteCategory.objects.filter(is_visible=True).order_by('display_order')
    hero_slides = WebsiteHeroSlide.objects.filter(is_active=True).order_by('display_order', '-created_at')

    hero = settings_data.hero_section
    product_block = settings_data.about_section
    about_summary = settings_data.about_section
    why_choose_us = settings_data.why_choose_us_section
    cta = settings_data.cta_section

    # Chosen Products (Featured)
    home_products = WebsiteProduct.objects.filter(is_featured=True, status=WebsiteProduct.Status.PUBLISHED).order_by('display_order')
    
    home_product_section = {
        "section_title": "Chosen Products",
        "section_subtitle": "",
    }

    return render(request, "public/index.html", {
        "settings": settings_data,
        "categories": categories,
        "hero_slides": hero_slides,
        "hero": hero,
        "product_block": product_block,
        "about_summary": about_summary,
        "why_choose_us": why_choose_us,
        "cta": cta,
        "home_products": home_products,
        "home_product_section": home_product_section,
    })

# ============================================================
# ABOUT VIEW
# ============================================================

def about(request):
    settings_data = WebsiteSettings.get_settings()
    pages = WebsitePage.objects.filter(status=WebsitePage.Status.PUBLISHED)

    return render(request, "public/about.html", {
        "settings": settings_data,
        "pages": pages,
    })

# ============================================================
# PRODUCTS VIEW
# ============================================================

def products(request):
    q = request.GET.get("q", "").strip()
    category_id_or_name = request.GET.get("category", "").strip()

    settings_data = WebsiteSettings.get_settings()
    categories = WebsiteCategory.objects.filter(is_visible=True).order_by('display_order')

    product_list = WebsiteProduct.objects.filter(status=WebsiteProduct.Status.PUBLISHED).select_related('inventory_product', 'website_category')

    selected_category_name = ""

    if category_id_or_name:
        # Check if it's an ID
        if category_id_or_name.isdigit():
            product_list = product_list.filter(website_category_id=category_id_or_name)
            cat = WebsiteCategory.objects.filter(id=category_id_or_name).first()
            if cat:
                selected_category_name = cat.name
        else:
            product_list = product_list.filter(website_category__name__iexact=category_id_or_name)
            selected_category_name = category_id_or_name

    if q:
        product_list = product_list.filter(
            Q(display_name__icontains=q) | 
            Q(inventory_product__name__icontains=q)
        )

    return render(request, "public/products.html", {
        "settings": settings_data,
        "categories": categories,
        "products": product_list,
        "q": q,
        "selected_category": category_id_or_name,
        "selected_category_name": selected_category_name,
    })

def product_detail(request, pk):
    settings_data = WebsiteSettings.get_settings()
    product = get_object_or_404(WebsiteProduct.objects.select_related('inventory_product'), pk=pk, status=WebsiteProduct.Status.PUBLISHED)

    related_products = []
    if product.website_category:
        related_products = WebsiteProduct.objects.filter(
            status=WebsiteProduct.Status.PUBLISHED,
            website_category=product.website_category
        ).exclude(id=product.id)[:4]

    return render(request, "public/product_detail.html", {
        "settings": settings_data,
        "product": product,
        "related_products": related_products,
    })

# ============================================================
# CONTACT VIEW
# ============================================================

def contact(request):
    settings_data = WebsiteSettings.get_settings()

    if request.method == "POST":
        name = request.POST.get("full_name") or request.POST.get("name", "")
        email = request.POST.get("email", "")
        phone = request.POST.get("phone", "")
        subject = request.POST.get("subject", "")
        message = request.POST.get("message", "")

        if name and email and message:
            WebsiteEnquiry.objects.create(
                name=name,
                email=email,
                phone=phone,
                subject=subject,
                message=message,
                ip_address=get_client_ip(request),
            )
            messages.success(request, "Your enquiry has been submitted successfully.")
            return redirect("contact")
        else:
            messages.error(request, "Please fill in all required fields.")

    return render(request, "public/contact.html", {
        "settings": settings_data,
    })

# ============================================================
# CUSTOM PAGE DETAIL VIEW
# ============================================================

def custom_page_detail(request, slug):
    settings_data = WebsiteSettings.get_settings()
    page = get_object_or_404(WebsitePage, slug=slug, status=WebsitePage.Status.PUBLISHED)

    return render(request, "public/page_detail.html", {
        "settings": settings_data,
        "page": page,
    })

# ============================================================
# BLOG VIEWS
# ============================================================
from .models import WebsiteBlogPost

def blog(request):
    settings_data = WebsiteSettings.get_settings()
    posts = WebsiteBlogPost.objects.filter(status=WebsiteBlogPost.Status.PUBLISHED)
    return render(request, "public/blog.html", {"settings": settings_data, "posts": posts})

def blog_detail(request, slug):
    settings_data = WebsiteSettings.get_settings()
    post = get_object_or_404(WebsiteBlogPost, slug=slug, status=WebsiteBlogPost.Status.PUBLISHED)
    return render(request, "public/blog_detail.html", {"settings": settings_data, "post": post})

# ============================================================
# CART HELPERS
# ============================================================

def get_cart(request):
    return request.session.get("cart", {})

def save_cart(request, cart):
    request.session["cart"] = cart
    request.session.modified = True

def safe_decimal(value, default="0.00"):
    try:
        if value in [None, ""]:
            return Decimal(default)
        return Decimal(str(value).replace(",", ""))
    except Exception:
        return Decimal(default)

def build_cart_items(request):
    cart = request.session.get("cart", {})
    items = []
    subtotal = Decimal("0.00")

    for product_id, item in cart.items():
        quantity = safe_decimal(item.get("quantity", "1"), "1")
        price = safe_decimal(item.get("price", "0.00"), "0.00")
        line_total = price * quantity

        estimated_weight_kg = safe_decimal(
            item.get("estimated_weight_kg") or item.get("weight_kg") or "0.000",
            "0.000"
        )
        line_weight_kg = estimated_weight_kg * quantity

        subtotal += line_total

        items.append({
            "id": item.get("id") or product_id,
            "product_id": product_id,
            "website_product_id": item.get("website_product_id") or product_id,
            "inventory_product_id": item.get("inventory_product_id"),
            "name": item.get("name", "Product"),
            "sku": item.get("sku", ""),
            "image": item.get("image", ""),
            "quantity": quantity,
            "price": price,
            "line_total": line_total,
            "estimated_weight_kg": estimated_weight_kg,
            "line_weight_kg": line_weight_kg,
        })

    return items, subtotal.quantize(Decimal("0.01"))

# ============================================================
# CART VIEWS
# ============================================================

def add_to_cart(request, pk):
    product = get_object_or_404(WebsiteProduct.objects.select_related('inventory_product'), pk=pk)

    try:
        quantity = int(request.POST.get("quantity", 1))
    except (ValueError, TypeError):
        quantity = 1

    if quantity < 1: quantity = 1
    if quantity > 99: quantity = 99

    product_name = product.get_display_name()
    product_price = product.get_price()
    product_image = product.main_image.url if product.main_image else ""
    estimated_weight_kg = product.inventory_product.estimated_weight_kg if hasattr(product.inventory_product, 'estimated_weight_kg') else 0

    inventory_product_id = product.inventory_product_id

    cart = get_cart(request)
    product_key = str(pk)

    if product_key in cart:
        existing_qty = int(cart[product_key].get("quantity", 0))
        new_qty = min(existing_qty + quantity, 99)
        cart[product_key]["quantity"] = new_qty
        cart[product_key]["name"] = product_name
        cart[product_key]["price"] = str(product_price)
        cart[product_key]["image"] = product_image
        cart[product_key]["inventory_product_id"] = inventory_product_id
        cart[product_key]["sku"] = product.inventory_product.product_id or ""
        cart[product_key]["estimated_weight_kg"] = str(estimated_weight_kg)
    else:
        cart[product_key] = {
            "product_id": pk,
            "website_product_id": pk,
            "inventory_product_id": inventory_product_id,
            "name": product_name,
            "price": str(product_price),
            "quantity": quantity,
            "image": product_image,
            "sku": product.inventory_product.product_id or "",
            "estimated_weight_kg": str(estimated_weight_kg),
        }

    save_cart(request, cart)
    messages.success(request, f"{product_name} added to cart.")
    return redirect(request.META.get('HTTP_REFERER', 'home'))

def cart_view(request):
    settings_data = WebsiteSettings.get_settings()
    items, subtotal = build_cart_items(request)

    return render(request, "public/cart.html", {
        "settings": settings_data,
        "cart_items": items,
        "subtotal": subtotal,
    })

def update_cart(request):
    if request.method == "POST":
        cart = get_cart(request)
        for key, value in request.POST.items():
            if key.startswith("qty_"):
                product_id = key.replace("qty_", "")
                try:
                    quantity = int(value)
                except ValueError:
                    quantity = 1

                if product_id in cart:
                    if quantity > 0:
                        cart[product_id]["quantity"] = quantity
                    else:
                        del cart[product_id]

        save_cart(request, cart)
        messages.success(request, "Cart updated.")

    return redirect(request.META.get('HTTP_REFERER', 'home'))

def remove_from_cart(request, pk):
    cart = get_cart(request)
    product_key = str(pk)
    if product_key in cart:
        del cart[product_key]
        save_cart(request, cart)
        messages.success(request, "Product removed from cart.")
    return redirect(request.META.get('HTTP_REFERER', 'home'))

# ============================================================
# CHECKOUT & DELIVERY LOGIC
# ============================================================

def checkout(request):
    settings_data = WebsiteSettings.get_settings()
    items, subtotal = build_cart_items(request)

    if not items:
        messages.warning(request, "Your cart is empty.")
        return redirect("cart")

    if request.method == "POST":
        # Process order
        customer_name = request.POST.get("customer_name", "").strip()
        if not customer_name:
            first_name = request.POST.get("first_name", "")
            last_name = request.POST.get("last_name", "")
            customer_name = f"{first_name} {last_name}".strip()
        email = request.POST.get("email", "")
        phone = request.POST.get("phone", "")
        address = request.POST.get("address", "")
        apartment = request.POST.get("apartment", "")
        city = request.POST.get("city", "")
        district = request.POST.get("district", "")
        province = request.POST.get("province", "")
        postal_code = request.POST.get("postal_code", "")
        payment_method = request.POST.get("payment_method", "COD")
        order_notes = request.POST.get("order_notes", "")

        full_address = f"{address}\n{apartment}\n{city}\n{postal_code}".strip()

        # Simple delivery logic calculation from checkout POST
        shipping_charge = Decimal(request.POST.get("calculated_shipping", "0"))
        total_amount = subtotal + shipping_charge

        order = WebsiteOrder.objects.create(
            website_order_number=f"WEB-{uuid.uuid4().hex[:6].upper()}",
            customer_name=customer_name,
            phone=phone,
            email=email,
            billing_address=full_address,
            shipping_address=full_address,
            city=city,
            district=district,
            province=province,
            subtotal=subtotal,
            shipping_charge=shipping_charge,
            total_amount=total_amount,
            payment_method=payment_method,
            internal_notes=order_notes,
        )

        for item in items:
            WebsiteOrderItem.objects.create(
                order=order,
                website_product_id=item["website_product_id"],
                inventory_product_id=item["inventory_product_id"],
                product_name=item["name"],
                sku=item["sku"],
                quantity=item["quantity"],
                unit_price=item["price"],
                line_total=item["line_total"],
            )

        # Clear cart
        request.session["cart"] = {}
        request.session.modified = True

        messages.success(request, "Order placed successfully! We will contact you soon.")

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                "success": True,
                "redirect_url": reverse("order_success", kwargs={"order_number": order.website_order_number})
            })

        return redirect("order_success", order_number=order.website_order_number)

    return render(request, "public/checkout.html", {
        "settings": settings_data,
        "cart_items": items,
        "subtotal": subtotal,
    })

def order_success(request, order_number=None):
    if not order_number:
        order_number = request.GET.get('order_number')
    
    return render(request, "public/order_success.html", {
        "order_number": order_number,
    })

def website_delivery_charge_api(request):
    """
    Called by JS in checkout.html
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"})
        
    import json
    try:
        data = json.loads(request.body)
        district = data.get("district", "").strip()
        weight_kg = safe_decimal(data.get("weight_kg", "0"))
        
        # Super simple delivery logic fallback (can be replaced with full logic later)
        if district.lower() in ["colombo", "gampaha", "kalutara"]:
            charge = Decimal("350") + (weight_kg - 1) * Decimal("50") if weight_kg > 1 else Decimal("350")
        else:
            charge = Decimal("450") + (weight_kg - 1) * Decimal("80") if weight_kg > 1 else Decimal("450")
            
        return JsonResponse({
            "success": True,
            "delivery_charge": str(charge),
        })
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})
