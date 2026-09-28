<?php
function travel_itinerary_query_args(array $request): array {
    $a = ['post_type' => 'itineraries', 'post_status' => 'publish', 'posts_per_page' => 12, 'paged' => max(1, absint($request['page'] ?? 1))];
    $slugs = [];
    foreach (explode(',', (string)($request['category'] ?? '')) as $p) { $s = sanitize_title(trim($p)); if ($s !== '') $slugs[] = $s; }
    if ($slugs) $a['tax_query'] = [['taxonomy' => 'itinerary_types', 'field' => 'slug', 'terms' => $slugs, 'operator' => 'IN']];
    $v = fn($x) => (is_int($x) && $x >= 0) ? $x : ((is_string($x) && ctype_digit($x)) ? (int)$x : null);
    $min = $v($request['min_days'] ?? null); $max = $v($request['max_days'] ?? null);
    if ($min !== null && $max !== null) { if ($min > $max) [$min, $max] = [$max, $min]; $a['meta_query'] = [['key' => 'trip_duration', 'value' => [$min, $max], 'compare' => 'BETWEEN', 'type' => 'NUMERIC']]; }
    elseif ($min !== null) $a['meta_query'] = [['key' => 'trip_duration', 'value' => $min, 'compare' => '>=', 'type' => 'NUMERIC']];
    elseif ($max !== null) $a['meta_query'] = [['key' => 'trip_duration', 'value' => $max, 'compare' => '<=', 'type' => 'NUMERIC']];
    $sort = $request['sort'] ?? '';
    if ($sort === 'price_asc' || $sort === 'price_desc') { $a['orderby'] = 'meta_value_num'; $a['meta_key'] = 'trip_price'; $a['order'] = $sort === 'price_asc' ? 'ASC' : 'DESC'; }
    else { $a['orderby'] = 'date'; $a['order'] = 'DESC'; }
    return $a;
}
