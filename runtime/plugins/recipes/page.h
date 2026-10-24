/* grade-sd Recipes: the menu page. Row n is recipe n + 1 of RECIPES/NAMES.TXT,
   whose name INSTALL writes to GRKIT_RECIPES. The page only records requests:
   the resident loader sees the new serial and applies RECIPES/Rnnn.TXT
   through the camera's own settings commands. */
#include "../../plugin.h"

static u32 recipe_count(volatile u32 *h) {
    u32 n=h[GRKIT_PLUGIN_RECIPES_COUNT/4];
    return n<GRKIT_RECIPE_MAX ? n : GRKIT_RECIPE_MAX;
}
static const u16 *recipe_name(volatile u32 *h,u32 row) {
    return (const u16 *)(GRKIT_RECIPES(h)+row*GRKIT_RECIPE_UNITS*2);
}
static const u16 *recipe_title(volatile u32 *h) { return text(h,TEXT_RECIPES); }
/* The root row names the recipe last applied. */
static const u16 *recipe_summary(volatile u32 *h) {
    u32 active=h[GRKIT_PLUGIN_RECIPES_ACTIVE/4];
    return active && active<=recipe_count(h) ? recipe_name(h,active-1) : text(h,TEXT_RECIPES);
}
static u32 recipe_rows(volatile u32 *h) { return recipe_count(h); }
static const u16 *recipe_label(volatile u32 *h,u32 row) { return recipe_name(h,row); }
static u32 recipe_icon(volatile u32 *h,u32 row) {
    (void)row;
    return GRKIT_ICON_TILE(h[GRKIT_HOST_MENU_LEVEL/4]==MENU_ROOT ? 0 : 1);
}
static u32 recipe_checked(volatile u32 *h,u32 row) {
    return h[GRKIT_PLUGIN_RECIPES_ACTIVE/4]==row+1;
}
/* Ask the resident loader for a recipe. A native recipe replaces a GRKit
   effect, which would otherwise keep overriding it. */
static void recipe_request(volatile u32 *h,u32 row) {
    h[GRKIT_HOST_ACTIVE/4]=0;
    if(h[GRKIT_PLUGIN_RECIPES_REQUEST/4]==row+1) return;
    h[GRKIT_PLUGIN_RECIPES_REQUEST/4]=row+1;
    ++h[GRKIT_PLUGIN_RECIPES_SERIAL/4];
}
/* OK keeps the recipe. A row that the preview already applied needs no
   second run. */
static void recipe_apply(volatile u32 *h,u32 row) {
    h[GRKIT_PLUGIN_RECIPES_ACTIVE/4]=row+1;
    recipe_request(h,row);
    ++h[GRKIT_HOST_MENU_APPLIES/4];
}
/* Highlighting a row previews it. When the page closes without OK, the
   loader applies the active recipe again. */
static void recipe_preview(volatile u32 *h) {
    u32 row=h[GRKIT_HOST_MENU_CURSOR/4];
    if(row<recipe_count(h)) recipe_request(h,row);
}
static u32 recipe_committed(volatile u32 *h) {
    u32 active=h[GRKIT_PLUGIN_RECIPES_ACTIVE/4];
    return active && active<=recipe_count(h) ? active-1 : 0;
}

#define RECIPES_PAGE {recipe_title,recipe_summary,recipe_rows,recipe_label,recipe_icon, \
    recipe_checked,recipe_apply,recipe_committed,recipe_preview,0,RECIPES_TILES}
