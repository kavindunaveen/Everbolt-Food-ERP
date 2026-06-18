from website.public_views import build_cart_items

def global_cart(request):
    """
    Context processor to make the cart items, subtotal, and count available 
    globally on all pages for the slide-out cart drawer.
    """
    items, subtotal = build_cart_items(request)
    
    # Calculate total number of unique items (or total quantity if preferred, here we do total items)
    cart_count = len(items)

    return {
        'cart_items': items,
        'cart_subtotal': subtotal,
        'cart_count': cart_count,
    }
