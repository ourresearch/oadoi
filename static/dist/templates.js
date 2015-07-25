angular.module('templates.app', ['article-page/article-page.tpl.html', 'landing-page/landing.tpl.html', 'profile-page/profile.tpl.html']);

angular.module("article-page/article-page.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("article-page/article-page.tpl.html",
    "<div class=\"article-page\">\n" +
    "   <div class=\"header\">\n" +
    "      <div class=\"articles-section\">\n" +
    "         <div class=\"article\" ng-show=\"ArticleService.data.article\">\n" +
    "            <div class=\"metrics\">\n" +
    "               <a href=\"/article/{{ ArticleService.data.article.pmid }}\"\n" +
    "                  tooltip-placement=\"left\"\n" +
    "                  tooltip=\"Citation percentile. Click to see comparison set.\"\n" +
    "                  class=\"percentile scale-{{ colorClass(ArticleService.data.article.percentile) }}\">\n" +
    "                  <span class=\"val\" ng-show=\"article.percentile !== null\">\n" +
    "                     {{ ArticleService.data.article.percentile }}\n" +
    "                  </span>\n" +
    "               </a>\n" +
    "               <span class=\"scopus scopus-small\"\n" +
    "                     tooltip-placement=\"left\"\n" +
    "                     tooltip=\"{{ article.citations }} citations via Scopus\">\n" +
    "                  {{ ArticleService.data.article.citations }}\n" +
    "               </span>\n" +
    "               <span class=\"loading\" ng-show=\"article.percentile === null\">\n" +
    "                  <i class=\"fa fa-refresh fa-spin\"></i>\n" +
    "               </span>\n" +
    "            </div>\n" +
    "\n" +
    "            <div class=\"article-biblio\">\n" +
    "               <span class=\"title\">{{ ArticleService.data.article.biblio.title }}</span>\n" +
    "               <span class=\"under-title\">\n" +
    "                  <span class=\"year\">({{ ArticleService.data.article.biblio.year }})</span>\n" +
    "                  <span class=\"authors\">{{ ArticleService.data.article.biblio.author_string }}</span>\n" +
    "                  <span class=\"journal\">{{ ArticleService.data.article.biblio.journal }}</span>\n" +
    "                  <a class=\"linkout\"\n" +
    "                     href=\"http://www.ncbi.nlm.nih.gov/pubmed/{{ ArticleService.data.article.biblio.pmid }}\">\n" +
    "                        <i class=\"fa fa-external-link\"></i>\n" +
    "                     </a>\n" +
    "               </span>\n" +
    "            </div>\n" +
    "         </div>\n" +
    "      </div>\n" +
    "   </div>\n" +
    "\n" +
    "   <div class=\"articles-infovis journal-dots\">\n" +
    "\n" +
    "      <ul class=\"journal-lines\">\n" +
    "         <li class=\"single-journal-line\" ng-repeat=\"journal in ArticleService.data.article.refset.journals.list\">\n" +
    "            <span class=\"journal-name\">\n" +
    "               {{ journal.name }}\n" +
    "               <span class=\"article-count\">\n" +
    "                  ({{ journal.num_articles }})\n" +
    "               </span>\n" +
    "            </span>\n" +
    "\n" +
    "\n" +
    "\n" +
    "            <div class=\"journal-articles-with-dots\">\n" +
    "               <a class=\"journal-article-dot\"\n" +
    "                  ng-repeat=\"article in journal.articles\"\n" +
    "                  style=\"{{ dotPosition(article.biblio.pmid, ArticleService.data.article.refset.journals.scopus_max_for_plot, article.scopus) }}\"\n" +
    "                  target=\"_blank\"\n" +
    "                  tooltip=\"{{ article.scopus }}: {{ article.biblio.title }}\"\n" +
    "                  href=\"http://www.ncbi.nlm.nih.gov/pubmed/{{ article.biblio.pmid }}\">\n" +
    "                  </a>\n" +
    "               <div class=\"median\"\n" +
    "                    tooltip=\"Median {{ journal.scopus_median }} citations\"\n" +
    "                    style=\"{{ medianPosition(ArticleService.data.article.refset.journals.scopus_max_for_plot, journal.scopus_median) }}\"></div>\n" +
    "               <div style=\"{{ medianPosition(ArticleService.data.article.refset.journals.scopus_max_for_plot, ArticleService.data.article.citations) }}\"\n" +
    "                    class=\"owner-article-scopus scale-{{ colorClass(ArticleService.data.article.percentile) }}\">\n" +
    "\n" +
    "               </div>\n" +
    "\n" +
    "            </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "         </li>\n" +
    "         <div class=\"fake-journal\">\n" +
    "         </div>\n" +
    "      </ul>\n" +
    "   </div>\n" +
    "</div>");
}]);

angular.module("landing-page/landing.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("landing-page/landing.tpl.html",
    "<div class=\"landing\">\n" +
    "\n" +
    "   Hi! heather and jason have both been here!\n" +
    "\n" +
    "</div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "");
}]);

angular.module("profile-page/profile.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("profile-page/profile.tpl.html",
    "<div class=\"profile-page\">\n" +
    "   <div class=\"header\">\n" +
    "      <h2>Citation report</h2>\n" +
    "   </div>\n" +
    "\n" +
    "   <div class=\"articles-section\">\n" +
    "      <ul class=\"articles\">\n" +
    "         <li ng-repeat=\"article in ProfileService.data.profile.articles | orderBy: ['is_calculating_percentile', '-is_old_enough_for_percentile', '-percentile', '-citations']\"\n" +
    "             class=\"article clearfix\">\n" +
    "\n" +
    "            <div class=\"metrics\">\n" +
    "               <a href=\"/article/{{ article.pmid }}\"\n" +
    "                  ng-show=\"article.is_old_enough_for_percentile && !article.is_calculating_percentile\"\n" +
    "                  tooltip-placement=\"left\"\n" +
    "                  tooltip=\"Citation percentile. Click to see comparison set.\"\n" +
    "                  class=\"percentile scale-{{ colorClass(article.percentile) }}\">\n" +
    "                  <span class=\"val\">\n" +
    "                     {{ article.percentile }}\n" +
    "                  </span>\n" +
    "               </a>\n" +
    "\n" +
    "               <span tooltip-placement=\"left\"\n" +
    "                     ng-show=\"!article.is_old_enough_for_percentile\"\n" +
    "                     tooltip=\"This is the tooltip\"\n" +
    "                     class=\"percentile too-new\">\n" +
    "                  too new\n" +
    "               </span>\n" +
    "\n" +
    "               <span class=\"scopus scopus-small\"\n" +
    "                     tooltip-placement=\"left\"\n" +
    "                     tooltip=\"{{ article.citations }} citations via Scopus\">\n" +
    "                  {{ article.citations }}\n" +
    "               </span>\n" +
    "               <span class=\"loading\" ng-show=\"article.is_calculating_percentile\">\n" +
    "                  <i class=\"fa fa-refresh fa-spin\"></i>\n" +
    "               </span>\n" +
    "            </div>\n" +
    "            <div class=\"article-biblio\">\n" +
    "               <span class=\"title\">{{ article.biblio.title }}</span>\n" +
    "               <span class=\"under-title\">\n" +
    "                  <span class=\"year\">({{ article.biblio.year }})</span>\n" +
    "                  <span class=\"authors\">{{ article.biblio.author_string }}</span>\n" +
    "                  <span class=\"journal\">{{ article.biblio.journal }}</span>\n" +
    "                  <a class=\"linkout\"\n" +
    "                     href=\"http://www.ncbi.nlm.nih.gov/pubmed/{{ article.pmid }}\">\n" +
    "                        <i class=\"fa fa-external-link\"></i>\n" +
    "                     </a>\n" +
    "               </span>\n" +
    "            </div>\n" +
    "\n" +
    "\n" +
    "         </li>\n" +
    "\n" +
    "\n" +
    "\n" +
    "      </ul>\n" +
    "\n" +
    "   </div>\n" +
    "</div>");
}]);
