angular.module('templates.app', ['article-page/article-page.tpl.html', 'landing-page/landing.tpl.html', 'profile-page/profile.tpl.html']);

angular.module("article-page/article-page.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("article-page/article-page.tpl.html",
    "<div class=\"article-page\">\n" +
    "   <div class=\"header\">\n" +
    "      <div class=\"article-biblio\">\n" +
    "         <span class=\"title\">{{ myArticle.biblio.title }}</span>\n" +
    "         <span class=\"under-title\">\n" +
    "            <span class=\"year\">({{ myArticle.biblio.year }})</span>\n" +
    "            <span class=\"authors\">{{ myArticle.biblio.author_string }}</span>\n" +
    "            <span class=\"journal\">{{ myArticle.biblio.journal }}</span>\n" +
    "            <a class=\"linkout\"\n" +
    "               href=\"http://www.ncbi.nlm.nih.gov/pubmed/{{ myArticle.biblio.pmid }}\">\n" +
    "                  <i class=\"fa fa-external-link\"></i>\n" +
    "               </a>\n" +
    "         </span>\n" +
    "      </div>\n" +
    "   </div>\n" +
    "\n" +
    "   <div class=\"refset-articles-section articles-section\">\n" +
    "      <h3>Reference articles</h3>\n" +
    "      <ul class=\"articles\">\n" +
    "         <li ng-repeat=\"article in refsetArticles | orderBy: '-scopusInt'\"\n" +
    "             class=\"article\">\n" +
    "\n" +
    "            <div class=\"metrics\">\n" +
    "               <span href=\"/article/{{ article.pmid }}\"\n" +
    "                  tooltip-placement=\"left\"\n" +
    "                  tooltip=\"Citations via Scopus\"\n" +
    "                  class=\"scopus-citations\">\n" +
    "                  {{ article.scopus }}\n" +
    "               </span>\n" +
    "            </div>\n" +
    "            <div class=\"article-biblio\">\n" +
    "               <span class=\"title\">{{ article.biblio.title }}</span>\n" +
    "               <span class=\"under-title\">\n" +
    "                  <span class=\"year\">({{ article.biblio.year }})</span>\n" +
    "                  <span class=\"authors\">{{ article.biblio.author_string }}</span>\n" +
    "                  <span class=\"journal\">{{ article.biblio.journal }}</span>\n" +
    "                  <a class=\"linkout\"\n" +
    "                     href=\"http://www.ncbi.nlm.nih.gov/pubmed/{{ article.biblio.pmid }}\">\n" +
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
    "   </div>\n" +
    "</div>");
}]);

angular.module("landing-page/landing.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("landing-page/landing.tpl.html",
    "<div class=\"landing\">\n" +
    "   <h1><img src=\"static/img/impactstory-biomed.png\" alt=\"Impactstory Biomed\"/></h1>\n" +
    "\n" +
    "\n" +
    "   <form class=\"create-profile\" ng-submit=\"makeProfile()\">\n" +
    "\n" +
    "      <div class=\"form-group\">\n" +
    "         <input type=\"text\"\n" +
    "                autofocus=\"autofocus\"\n" +
    "                class=\"form-control input-lg\"\n" +
    "                ng-model=\"newProfile.name\"\n" +
    "                placeholder=\"What is your name?\"/>\n" +
    "\n" +
    "      </div>\n" +
    "\n" +
    "      <div class=\"form-group\">\n" +
    "         <textarea class=\"form-control input-lg\"\n" +
    "                   ng-model=\"newProfile.pmids\"\n" +
    "                   placeholder=\"What are your PubMed IDs?\"\n" +
    "                   rows=\"5\"></textarea>\n" +
    "\n" +
    "      </div>\n" +
    "      <div class=\"submit-btn-container\">\n" +
    "         <button type=\"submit\" class=\"btn submit btn-lg btn-default\">\n" +
    "            Find my impact\n" +
    "         </button>\n" +
    "      </div>\n" +
    "\n" +
    "   </form>\n" +
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
    "         <li ng-repeat=\"article in ProfileService.data.profile.articles | orderBy: '-percentile'\"\n" +
    "             class=\"article\">\n" +
    "\n" +
    "            <div class=\"metrics\">\n" +
    "               <a href=\"/article/{{ article.pmid }}\"\n" +
    "                  tooltip-placement=\"left\"\n" +
    "                  tooltip=\"Percentile compared to related articles. Click to see reference set.\"\n" +
    "                  class=\"percentile scale-{{ colorClass(article.percentile) }}\">\n" +
    "                  <span class=\"val\" ng-show=\"article.percentile !== null\">\n" +
    "                     {{ article.percentile }}\n" +
    "                  </span>\n" +
    "                  <span class=\"loading\" ng-show=\"article.percentile === null\">\n" +
    "                     <i class=\"fa fa-refresh fa-spin\"></i>\n" +
    "                  </span>\n" +
    "\n" +
    "               </a>\n" +
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
