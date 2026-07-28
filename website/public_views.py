import time
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse, HttpResponse, HttpResponseGone
from django.db.models import Q
import uuid
import threading
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
import requests

from .models import (
    WebsiteSettings, WebsiteCategory, WebsiteProduct,
    WebsitePage, WebsiteEnquiry, WebsiteOrder, WebsiteOrderItem, WebsiteHeroSlide
)
from crm.models import Customer
from sales.models import Invoice, InvoiceItem
from inventory.models import Product, StockReserve

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

    seo_title = ""
    meta_description = ""
    focus_keyword = ""
    og_image = None
    
    if category_id_or_name:
        # Check if it's an ID
        if category_id_or_name.isdigit():
            product_list = product_list.filter(website_category_id=category_id_or_name)
            cat = WebsiteCategory.objects.filter(id=category_id_or_name).first()
            if cat:
                selected_category_name = cat.name
                seo_title = cat.meta_title or cat.name
                meta_description = cat.meta_description or cat.description[:155]
                focus_keyword = cat.focus_keyword
                og_image = cat.image.url if cat.image else None
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
        "seo_title": seo_title,
        "meta_description": meta_description,
        "focus_keyword": focus_keyword,
        "og_image": og_image,
    })

def product_detail(request, pk):
    settings_data = WebsiteSettings.get_settings()
    product = get_object_or_404(WebsiteProduct.objects.select_related('inventory_product').prefetch_related('variants__inventory_product'), pk=pk, status=WebsiteProduct.Status.PUBLISHED)

    related_products = []
    if product.website_category:
        related_products = WebsiteProduct.objects.filter(
            status=WebsiteProduct.Status.PUBLISHED,
            website_category=product.website_category
        ).exclude(id=product.id)[:4]

    import json
    variants_json = []
    if product.variants.exists():
        variants_json.append({
            'id': str(product.inventory_product.id),
            'name': 'Default / Standard',
            'price': float(product.get_price()),
            'stock': float(product.inventory_product.available_stock),
            'sku': product.inventory_product.product_id or '',
            'unit': product.inventory_product.get_stock_unit_display() or ''
        })
        for v in product.variants.all():
            price = round(v.inventory_product.selling_price * Decimal('1.18'), 2)
            variants_json.append({
                'id': str(v.inventory_product.id),
                'name': v.variant_name,
                'price': float(price),
                'stock': float(v.inventory_product.available_stock),
                'sku': v.inventory_product.product_id or '',
                'unit': v.inventory_product.get_stock_unit_display() or ''
            })

    price_tiers = []
    if product.inventory_product:
        for t in product.inventory_product.price_tiers.order_by('min_quantity'):
            price_tiers.append({
                'min_quantity': t.min_quantity,
                'price': round(t.price * Decimal('1.18'), 2)
            })

    return render(request, "public/product_detail.html", {
        "settings": settings_data,
        "product": product,
        "variants_json": variants_json,
        "variants_json_str": json.dumps(variants_json),
        "price_tiers": price_tiers,
        "related_products": related_products,
        "seo_title": product.meta_title or product.get_display_name(),
        "meta_description": product.meta_description or product.short_description or product.description[:155],
        "focus_keyword": product.focus_keyword,
        "og_image": product.main_image.url if product.main_image else None,
        "cart_item_count": sum(item.get("quantity", 0) for item in request.session.get("cart", {}).values()),
    })

# ============================================================
# CONTACT VIEW
# ============================================================

def contact(request):
    settings_data = WebsiteSettings.get_settings()

    if request.method == "POST":
        # Spam Protection (Honeypot)
        if request.POST.get("website_url"):
            messages.success(request, "Your message has been sent successfully. We will get back to you soon!")
            return redirect("public_contact")

        name = request.POST.get("full_name") or request.POST.get("name", "")
        email = request.POST.get("email", "")
        phone = request.POST.get("phone", "")
        subject = request.POST.get("subject", "")
        message = request.POST.get("message", "")

        # reCAPTCHA Validation
        recaptcha_response = request.POST.get('g-recaptcha-response')
        recaptcha_secret_key = getattr(settings, 'RECAPTCHA_PRIVATE_KEY', None)
        
        if recaptcha_secret_key:
            if not recaptcha_response:
                messages.error(request, "Please tick the reCAPTCHA box to prove you are human.")
                return redirect("contact")
            
            data = {
                'secret': recaptcha_secret_key,
                'response': recaptcha_response
            }
            try:
                r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
                result = r.json()
                if not result.get('success'):
                    messages.error(request, "reCAPTCHA validation failed. Please try again.")
                    return redirect("contact")
            except Exception as e:
                messages.error(request, "Error connecting to reCAPTCHA service. Please try again.")
                return redirect("contact")

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
        "recaptcha_site_key": getattr(settings, 'RECAPTCHA_PUBLIC_KEY', None),
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
        "seo_title": page.meta_title or page.title,
        "meta_description": page.meta_description,
        "focus_keyword": page.focus_keyword,
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
        min_order_qty = 1
        
        inv_id = item.get("inventory_product_id")
        website_product_id = item.get("website_product_id") or product_id.split('_')[0]
        
        if inv_id:
            from inventory.models import Product
            try:
                inv_product = Product.objects.prefetch_related('price_tiers').get(id=inv_id)
                best_price = inv_product.selling_price
                for tier in inv_product.price_tiers.order_by('-min_quantity'):
                    if quantity >= tier.min_quantity:
                        best_price = tier.price
                        break
                price = round(best_price * Decimal('1.18'), 2)
            except Product.DoesNotExist:
                pass

        # Fetch min_order_qty from the website product
        try:
            wp = WebsiteProduct.objects.get(pk=website_product_id)
            min_order_qty = wp.min_order_qty or 1
        except (WebsiteProduct.DoesNotExist, ValueError):
            pass

        line_total = price * quantity

        estimated_weight_kg = safe_decimal(
            item.get("estimated_weight_kg") or item.get("weight_kg") or "0.000",
            "0.000"
        )
        line_weight_kg = estimated_weight_kg * quantity

        subtotal += line_total

        items.append({
            "id": product_id,
            "product_id": product_id,
            "website_product_id": website_product_id,
            "inventory_product_id": item.get("inventory_product_id"),
            "name": item.get("name", "Product"),
            "sku": item.get("sku", ""),
            "image": item.get("image", ""),
            "quantity": quantity,
            "price": price,
            "line_total": line_total,
            "estimated_weight_kg": estimated_weight_kg,
            "line_weight_kg": line_weight_kg,
            "min_order_qty": min_order_qty,
        })

    return items, subtotal.quantize(Decimal("0.01"))

# ============================================================
# CART VIEWS
# ============================================================

def add_to_cart(request, pk):
    product = get_object_or_404(WebsiteProduct.objects.select_related('inventory_product'), pk=pk)

    if product.inventory_product and product.inventory_product.available_stock <= 0:
        messages.error(request, f"{product.get_display_name()} is currently out of stock.")
        return redirect(request.META.get('HTTP_REFERER', reverse('products')))

    try:
        quantity = int(request.POST.get("quantity", 1))
    except (ValueError, TypeError):
        quantity = 1

    min_qty = getattr(product, 'min_order_qty', 1) or 1

    # Strict MOQ enforcement — block, do NOT silently bump
    if quantity < min_qty:
        if min_qty == 1:
            messages.error(request, f"Please enter a valid quantity to add {product.get_display_name()} to your cart.")
        else:
            messages.error(
                request,
                f"\u26a0\ufe0f Minimum order quantity for '{product.get_display_name()}' is {min_qty} unit{'s' if min_qty > 1 else ''}. "
                f"Please add at least {min_qty} to proceed."
            )
        return redirect(request.META.get('HTTP_REFERER', reverse('products')))

    if quantity > 9999: quantity = 9999

    inventory_product_id_post = request.POST.get('inventory_product_id')
    inv_product = None
    if inventory_product_id_post:
        from inventory.models import Product
        inv_product = get_object_or_404(Product, pk=inventory_product_id_post)
        if not (inv_product == product.inventory_product or product.variants.filter(inventory_product=inv_product).exists()):
            messages.error(request, "Invalid variant selected.")
            return redirect(request.META.get('HTTP_REFERER', reverse('products')))
            
        product_price = round(inv_product.selling_price * Decimal('1.18'), 2)
        estimated_weight_kg = getattr(inv_product, 'estimated_weight_kg', 0)
        variant = product.variants.filter(inventory_product=inv_product).first()
        if variant:
            product_name = f"{product.get_display_name()} - {variant.variant_name}"
        else:
            product_name = f"{product.get_display_name()} - Default"
        inventory_product_id = inv_product.id
        stock_to_check = inv_product.available_stock
    else:
        inv_product = product.inventory_product
        product_name = product.get_display_name()
        product_price = product.get_price()
        estimated_weight_kg = getattr(product.inventory_product, 'estimated_weight_kg', 0)
        inventory_product_id = product.inventory_product_id
        stock_to_check = product.inventory_product.available_stock if product.inventory_product else 0

    product_image = product.main_image.url if product.main_image else ""
    cart = get_cart(request)
    product_key = f"{pk}_{inventory_product_id}"

    if product_key in cart:
        existing_qty = int(cart[product_key].get("quantity", 0))
        new_qty = existing_qty + quantity
        
        if inv_product and new_qty > stock_to_check:
            messages.error(request, f"Cannot add {quantity} more. Insufficient stock available.")
            return redirect(request.META.get('HTTP_REFERER', reverse('products')))
            
        cart[product_key]["quantity"] = min(new_qty, 9999)
        cart[product_key]["name"] = product_name
        cart[product_key]["price"] = str(product_price)
        cart[product_key]["image"] = product_image
        cart[product_key]["inventory_product_id"] = inventory_product_id
        cart[product_key]["sku"] = inv_product.product_id if inv_product else ""
        cart[product_key]["estimated_weight_kg"] = str(estimated_weight_kg)
    else:
        if inv_product and quantity > stock_to_check:
            messages.error(request, f"Cannot add {quantity}. Insufficient stock available.")
            return redirect(request.META.get('HTTP_REFERER', reverse('products')))
            
        cart[product_key] = {
            "product_id": pk,
            "website_product_id": pk,
            "inventory_product_id": inventory_product_id,
            "name": product_name,
            "price": str(product_price),
            "quantity": quantity,
            "image": product_image,
            "sku": inv_product.product_id if inv_product else "",
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
                        try:
                            website_product_id = product_id.split('_')[0]
                            inventory_product_id = product_id.split('_')[1] if '_' in product_id else None
                            
                            product = WebsiteProduct.objects.prefetch_related('variants__inventory_product').select_related('inventory_product').get(pk=website_product_id)
                            
                            inv_product = None
                            if inventory_product_id:
                                if str(product.inventory_product.id) == inventory_product_id:
                                    inv_product = product.inventory_product
                                else:
                                    for v in product.variants.all():
                                        if str(v.inventory_product.id) == inventory_product_id:
                                            inv_product = v.inventory_product
                                            break
                            else:
                                inv_product = product.inventory_product
                                
                            min_qty = getattr(product, 'min_order_qty', 1) or 1
                            if quantity < min_qty:
                                messages.error(
                                    request,
                                    f"Quantity for '{cart[product_id]['name']}' cannot be below the minimum order quantity of {min_qty}."
                                )
                            elif inv_product and quantity > inv_product.available_stock:
                                messages.warning(request, f"Reduced '{cart[product_id]['name']}' due to insufficient stock.")
                                cart[product_id]["quantity"] = int(inv_product.available_stock)
                            else:
                                cart[product_id]["quantity"] = quantity
                        except WebsiteProduct.DoesNotExist:
                            del cart[product_id]
                    else:
                        del cart[product_id]

        save_cart(request, cart)
        # Only show generic success if there were no error-level messages queued
        from django.contrib.messages import get_messages
        storage = get_messages(request)
        stored = list(storage)  # consume so they aren't lost
        has_errors = any(m.level_tag in ('error', 'warning') for m in stored)
        for m in stored:
            messages.add_message(request, m.level, str(m))
        if not has_errors:
            messages.success(request, "Cart updated successfully.")

    return redirect(request.META.get('HTTP_REFERER', 'home'))

def remove_from_cart(request, pk):
    """Remove item from cart. pk may be the numeric website product ID or the full cart key."""
    cart = get_cart(request)
    # Cart keys are in format "{website_product_id}_{inventory_product_id}"
    # Try to find an exact match first, then search by prefix
    product_key = None
    pk_str = str(pk)
    if pk_str in cart:
        product_key = pk_str
    else:
        # Search for a key starting with this pk
        for key in list(cart.keys()):
            if key.startswith(pk_str + '_') or key == pk_str:
                product_key = key
                break

    if product_key:
        name = cart[product_key].get("name", "Product")
        del cart[product_key]
        save_cart(request, cart)
        messages.success(request, f"{name} removed from cart.")
    return redirect(request.META.get('HTTP_REFERER', 'home'))

# ============================================================
# CHECKOUT & DELIVERY LOGIC
# ============================================================

def checkout(request):
    settings_data = WebsiteSettings.get_settings()
    items, subtotal = build_cart_items(request)

    if not items:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({"success": False, "message": "Your cart is empty."})
        messages.warning(request, "Your cart is empty.")
        return redirect("cart")

    if request.method == "POST":
        # Spam Protection (Honeypot)
        if request.POST.get("website_url"):
            messages.success(request, "Order placed successfully.")
            return redirect("public_home")

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

        # Secure delivery logic calculation from server side
        cart_weight_kg = Decimal(request.session.get("cart_weight_kg", 0))
        shipping_charge = calculate_delivery_cost(district, city, cart_weight_kg)
        total_amount = subtotal + shipping_charge
        
        # Final strict stock check before order creation
        for item in items:
            product = get_object_or_404(WebsiteProduct.objects.select_related('inventory_product'), pk=item["website_product_id"])
            if product.inventory_product and item["quantity"] > product.inventory_product.available_stock:
                msg = f"Sorry, {product.get_display_name()} does not have sufficient stock for your requested quantity. Please update your cart."
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({"success": False, "message": msg})
                messages.error(request, msg)
                return redirect("cart")

        order = WebsiteOrder.objects.create(
            website_order_number=f"WEB-{uuid.uuid4().hex[:6].upper()}",
            user=request.user if request.user.is_authenticated else None,
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
            
            # Create StockReserve for 7 days
            try:
                from django.utils import timezone
                from datetime import timedelta
                expiry = timezone.now() + timedelta(days=7)
                inv_product = Product.objects.get(id=item["inventory_product_id"])
                StockReserve.objects.create(
                    product=inv_product,
                    quantity=item["quantity"],
                    reference_type='WEB_ORDER',
                    reference_id=order.id,
                    expiry_time=expiry
                )
            except Exception as e:
                print(f"Failed to reserve stock: {e}")

        # System Notifications for Admins
        try:
            from users.models import Notification as ErbNotification, User as ErbUser
            admin_recipients = ErbUser.objects.filter(
                Q(is_superuser=True) | Q(role__name='Administrator')
            ).filter(is_active=True).distinct()

            if not admin_recipients.exists():
                print(f"[WEBSITE ORDER] WARNING: No admin recipients found for notification! Order: {order.website_order_number}")
            
            notif_count = 0
            for admin in admin_recipients:
                ErbNotification.objects.create(
                    recipient=admin,
                    notification_type='info',
                    title=f"🛒 New Website Order: {order.website_order_number}",
                    message=f"Rs {order.total_amount} order by {order.customer_name} ({order.phone}). District: {order.district}.",
                    link=reverse("website_order_detail", kwargs={'pk': order.pk})
                )
                notif_count += 1
                print(f"[WEBSITE ORDER] Notification sent to admin: {admin.username}")
            
            print(f"[WEBSITE ORDER] {notif_count} notification(s) created for order {order.website_order_number}")
        except Exception as notif_error:
            # Never let notification failure break the order confirmation
            import traceback
            print(f"[WEBSITE ORDER] ERROR creating notifications for {order.website_order_number}: {notif_error}")
            print(traceback.format_exc())

        # Send Emails Async to avoid blocking
        def send_order_emails(order_obj, order_items_list, settings_obj):
            try:
                # 1. Send to Customer
                if order_obj.email:
                    subject = f"Order Confirmation - {order_obj.website_order_number}"
                    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@organicfoodslanka.com')
                    context = {'order': order_obj, 'items': order_items_list}
                    
                    text_content = render_to_string('emails/order_confirmation.txt', context)
                    html_content = render_to_string('emails/order_confirmation.html', context)
                    
                    msg = EmailMultiAlternatives(subject, text_content, from_email, [order_obj.email])
                    msg.attach_alternative(html_content, "text/html")
                    msg.send(fail_silently=True)

                # 2. Send Admin Alerts
                admin_emails_raw = getattr(settings_obj, 'order_notification_emails', '')
                if admin_emails_raw:
                    admin_emails = [e.strip() for e in admin_emails_raw.split(',') if e.strip()]
                    if admin_emails:
                        admin_subject = f"New Order Alert: {order_obj.website_order_number}"
                        admin_context = {'order': order_obj, 'items': order_items_list}
                        
                        admin_text = render_to_string('emails/admin_order_alert.txt', admin_context)
                        admin_html = render_to_string('emails/admin_order_alert.html', admin_context)
                        
                        admin_msg = EmailMultiAlternatives(admin_subject, admin_text, from_email, admin_emails)
                        admin_msg.attach_alternative(admin_html, "text/html")
                        admin_msg.send(fail_silently=True)
            except Exception as e:
                print(f"Error sending emails: {e}")

        order_items_data = [
            {
                "product_name": i["name"], 
                "quantity": i["quantity"], 
                "line_total": i["line_total"]
            } for i in items
        ]
        threading.Thread(target=send_order_emails, args=(order, order_items_data, settings_data)).start()

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
        "cart_weight_kg": sum(item["line_weight_kg"] for item in items),
    })

def order_success(request, order_number=None):
    if not order_number:
        order_number = request.GET.get('order_number')
    
    return render(request, "public/order_success.html", {
        "order_number": order_number,
    })

def calculate_delivery_cost(district, city, weight_kg):
    from decimal import Decimal
    chargeable_weight = max(Decimal("1"), Decimal(round(weight_kg)))
    
    colombo_1_15 = [
        "Colombo 01 – Fort", "Colombo 02 – Slave Island", "Colombo 03 – Kollupitiya", "Colombo 04 – Bambalapitiya",
        "Colombo 05 – Havelock Town", "Colombo 06 – Wellawatte", "Colombo 07 – Cinnamon Gardens", "Colombo 08 – Borella",
        "Colombo 09 – Dematagoda", "Colombo 10 – Maradana", "Colombo 11 – Pettah", "Colombo 12 – Hulftsdorp",
        "Colombo 13 – Kotahena", "Colombo 14 – Grandpass", "Colombo 15 – Modara"
    ]
    
    colombo_suburbs = [
        "Dehiwala", "Mount Lavinia", "Ratmalana", "Moratuwa", "Maharagama", "Nugegoda", "Kohuwala", "Piliyandala",
        "Kesbewa", "Kottawa", "Homagama", "Battaramulla", "Kotte (Sri Jayawardenepura Kotte)", "Rajagiriya",
        "Malabe", "Talawatugoda", "Pelawatte", "Athurugiriya", "Pannipitiya", "Kaduwela", "Angoda", "Kolonnawa",
        "Wellampitiya", "Kelaniya", "Wattala (bordering Colombo)"
    ]
    
    far_districts = [
        "Jaffna", "Kilinochchi", "Mannar", "Mullaitivu", "Vavuniya", "Trincomalee", "Batticaloa", "Ampara"
    ]
    
    if district == "Colombo":
        if city in colombo_1_15:
            base = Decimal("350")
            extra = Decimal("100")
        elif city in colombo_suburbs:
            base = Decimal("400")
            extra = Decimal("100")
        else:
            base = Decimal("450")
            extra = Decimal("100")
    elif district in far_districts:
        base = Decimal("500")
        extra = Decimal("125")
    else:
        base = Decimal("450")
        extra = Decimal("100")
        
    extra_weight = max(Decimal("0"), chargeable_weight - Decimal("1"))
    charge = base + (extra_weight * extra)
    return charge

def website_delivery_charge_api(request):
    """
    Called by JS in checkout.html
    """
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Invalid request"})
        
    try:
        if request.content_type == 'application/json':
            import json
            data = json.loads(request.body)
        else:
            data = request.POST

        district = data.get("district", "").strip()
        city = data.get("city", "").strip()
        weight_kg = safe_decimal(data.get("weight_kg", "0"))
        
        charge = calculate_delivery_cost(district, city, weight_kg)
            
        return JsonResponse({
            "success": True,
            "delivery_charge": str(charge),
        })
    except Exception as e:
        return JsonResponse({"success": False, "message": str(e)})

# ============================================================
# SEO SITEMAP & ROBOTS.TXT
# ============================================================
from django.http import HttpResponse
from datetime import datetime

# ============================================================
# SEO: ROBOTS.TXT & SITEMAP.XML
# ============================================================
def robots_txt(request):
    host = request.get_host().lower()
    erp_hosts = ['erp.organicfoodslanka.com', 'staging.organicfoodslanka.com']
    
    # Hide ERP subdomains from search engines completely
    if any(h in host for h in erp_hosts):
        lines = [
            "User-agent: *",
            "Disallow: /"
        ]
    else:
        lines = [
            "User-agent: *",
            "Allow: /",
            "",
            "# Disallow transactional / private pages",
            "Disallow: /cart/",
            "Disallow: /checkout/",
            "Disallow: /order-success/",
            "Disallow: /login/",
            "Disallow: /register/",
            "Disallow: /my-account/",
            "Disallow: /password-reset/",
            "Disallow: /search/",
            "",
            "# Block WordPress paths that no longer exist",
            "Disallow: /wp-admin/",
            "Disallow: /wp-login.php",
            "Disallow: /wp-content/",
            "Disallow: /wp-includes/",
            "",
            f"Sitemap: {request.scheme}://organicfoodslanka.com/sitemap.xml"
        ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request):
    """Clean sitemap containing only new website URLs."""
    products = WebsiteProduct.objects.filter(status=WebsiteProduct.Status.PUBLISHED)
    categories = WebsiteCategory.objects.filter(is_visible=True)
    pages = WebsitePage.objects.filter(status=WebsitePage.Status.PUBLISHED)

    # Always use canonical domain for sitemap
    host_url = "https://organicfoodslanka.com"
    today = datetime.now().strftime("%Y-%m-%d")

    xml = ['<?xml version="1.0" encoding="UTF-8"?>']
    xml.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    # ---- Static core pages ----
    static_pages = [
        ("/",                     "daily",   "1.0"),
        ("/about/",               "monthly", "0.8"),
        ("/products/",            "daily",   "0.9"),
        ("/contact/",             "monthly", "0.7"),
        ("/blog/",                "weekly",  "0.7"),
        ("/privacy-policy/",      "yearly",  "0.4"),
        ("/terms-and-conditions/","yearly",  "0.4"),
        ("/delivery-charges/",    "monthly", "0.5"),
    ]
    for path, freq, prio in static_pages:
        xml.append(f"<url><loc>{host_url}{path}</loc><lastmod>{today}</lastmod><changefreq>{freq}</changefreq><priority>{prio}</priority></url>")

    # ---- Product detail pages ----
    for p in products:
        loc = f"{host_url}/products/{p.id}/"
        lastmod = p.updated_at.strftime('%Y-%m-%d') if hasattr(p, 'updated_at') and p.updated_at else today
        xml.append(f"<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>")

    # ---- Category filter pages ----
    for c in categories:
        loc = f"{host_url}/products/?category={c.id}"
        xml.append(f"<url><loc>{loc}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>")

    # ---- CMS custom pages ----
    for pg in pages:
        loc = f"{host_url}/{pg.slug}/"
        lastmod = pg.updated_at.strftime('%Y-%m-%d') if hasattr(pg, 'updated_at') and pg.updated_at else today
        xml.append(f"<url><loc>{loc}</loc><lastmod>{lastmod}</lastmod><changefreq>monthly</changefreq><priority>0.6</priority></url>")

    xml.append('</urlset>')
    return HttpResponse("\n".join(xml), content_type="application/xml")


# ============================================================
# SEO: LEGACY WORDPRESS 301 REDIRECTS
# ============================================================
def wp_legacy_redirect(request):
    """
    301 Permanent Redirects for old WordPress URLs.
    Maps old /product/, /product-category/ and other WP slugs
    to their closest matching new page.
    """
    path = request.path.rstrip('/')

    # ---- Exact page redirects ----
    exact_redirects = {
        '/about-us':                                   '/about/',
        '/contact-us':                                 '/contact/',
        '/shop':                                       '/products/',
        '/organic-products':                           '/products/',
        '/hotel-supplies':                             '/products/?category=6',
        '/tea-blended-products':                       '/products/?category=1',
        '/privacy-policy':                             '/privacy-policy/',
        '/terms-conditions':                           '/terms-and-conditions/',
        '/delivery-returns':                           '/delivery-charges/',

        # Blog post
        '/how-to-make-sri-lankan-milk-tea-kiri-tea-authentic-easy-recipe': '/blog/',

        # WP sitemaps — point to new sitemap
        '/sitemap_index.xml':   '/sitemap.xml',
        '/wp-sitemap.xml':      '/sitemap.xml',
        '/page-sitemap.xml':    '/sitemap.xml',
        '/product-sitemap.xml': '/sitemap.xml',
        '/category-sitemap.xml':'/sitemap.xml',
    }

    if path in exact_redirects:
        return redirect(exact_redirects[path], permanent=True)

    # ---- Product category redirects ----
    category_map = {
        '/product-category/flavoured-tea':    '/products/?category=1',
        '/product-category/herbal-teas':      '/products/?category=2',
        '/product-category/kithul-products':  '/products/?category=5',
        '/product-category/everleaf-tea-range': '/products/?category=4',
        '/product-category/powder-packets':   '/products/?category=3',
        '/product-category/sachet-packets':   '/products/',
    }
    if path in category_map:
        return redirect(category_map[path], permanent=True)

    # ---- Individual product redirects (old slug → best matching new product page) ----
    # We send them to the main products listing since product IDs differ
    product_map = {
        '/product/dehydrated-papaya':          '/products/',
        '/product/dehydrated-mixed-fruit':     '/products/',
        '/product/curry-leaves-powder':        '/products/?category=3',
        '/product/dehydrated-bitter-gourd':    '/products/',
        '/product/beetroot-powder':            '/products/?category=3',
        '/product/creamer-sachet':             '/products/',
        '/product/dehydrated-banana':          '/products/',
        '/product/dehydrated-breadfruit':      '/products/',
        '/product/tomato-powder':              '/products/?category=3',
        '/product/curry-powder':               '/products/?category=3',
        '/product/pumpkin-powder':             '/products/?category=3',
        '/product/carrot-powder':              '/products/?category=3',
        '/product/dehydrated-curry-leaves':    '/products/',
        '/product/everleaf-pure-ceylon-tea':   '/products/?category=4',
        '/product/dehydrated-jackfruit':       '/products/',
        '/product/dried-moringa-powder':       '/products/?category=3',
        '/product/ushma':                      '/products/',
        '/product/brown-sugar-sachet':         '/products/',
        '/product/slim-herb-tea':              '/products/?category=2',
    }
    if path in product_map:
        return redirect(product_map[path], permanent=True)

    # ---- wp-content uploads: PDF catalogue — 410 Gone ----
    if path.startswith('/wp-content/'):
        return HttpResponseGone()

    # ---- Everything else: 404 ----
    from django.http import Http404
    raise Http404

# ============================================================
# CUSTOMER AUTHENTICATION & ACCOUNT
# ============================================================
from django.contrib.auth import authenticate, login, logout
from users.models import User, Role
from django.contrib.auth.decorators import login_required

def register_view(request):
    settings_data = WebsiteSettings.get_settings()
    if request.user.is_authenticated:
        return redirect('public_my_account')

    if request.method == "POST":
        # Spam Protection (Honeypot)
        if request.POST.get("website_url"):
            messages.success(request, "Account created successfully!")
            return redirect("public_login")
            
        # reCAPTCHA Validation
        recaptcha_response = request.POST.get('g-recaptcha-response')
        recaptcha_secret_key = getattr(settings, 'RECAPTCHA_PRIVATE_KEY', None)
        
        if recaptcha_secret_key:
            if not recaptcha_response:
                messages.error(request, "Please tick the reCAPTCHA box to prove you are human.")
                return redirect("public_register")
            
            data = {
                'secret': recaptcha_secret_key,
                'response': recaptcha_response
            }
            try:
                r = requests.post('https://www.google.com/recaptcha/api/siteverify', data=data)
                result = r.json()
                if not result.get('success'):
                    messages.error(request, "reCAPTCHA validation failed. Please try again.")
                    return redirect("public_register")
            except Exception as e:
                messages.error(request, "Error connecting to reCAPTCHA service. Please try again.")
                return redirect("public_register")

        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        if User.objects.filter(email=email).exists() or User.objects.filter(username=email).exists():
            messages.error(request, "An account with this email already exists.")
            return redirect('public_register')

        try:
            role, created = Role.objects.get_or_create(
                name="Website Customer",
                defaults={'description': "Customers registered via the public website.", 'is_system': True}
            )
            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                role=role
            )
            login(request, user)
            messages.success(request, "Registration successful! Welcome to Organic Foods Lanka.")
            next_url = request.POST.get('next') or request.GET.get('next') or 'public_my_account'
            return redirect(next_url)
        except Exception as e:
            messages.error(request, f"Registration failed: {str(e)}")

    return render(request, "public/register.html", {
        "settings": settings_data,
        "recaptcha_site_key": getattr(settings, 'RECAPTCHA_PUBLIC_KEY', None),
    })

def login_view(request):
    settings_data = WebsiteSettings.get_settings()
    if request.user.is_authenticated:
        return redirect('public_my_account')

    if request.method == "POST":
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Login successful!")
            next_url = request.POST.get('next') or request.GET.get('next') or 'public_my_account'
            return redirect(next_url)
        else:
            messages.error(request, "Invalid email or password.")

    return render(request, "public/login.html", {"settings": settings_data})

def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('home')

@login_required(login_url='/public/login/')
def my_account(request):
    settings_data = WebsiteSettings.get_settings()
    orders = WebsiteOrder.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, "public/my_account.html", {
        "settings": settings_data,
        "orders": orders
    })
