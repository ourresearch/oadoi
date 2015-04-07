/* yay impactstory */
angular.module('app', [
  'ngRoute', // loaded from external lib
  'templates.app',  // this is how it accesses the cached templates in ti.js
  'ui.bootstrap',

  'landingPage',
  'profilePage',
  'articlePage'
]);




angular.module('app').config(function ($routeProvider,
                                       $locationProvider) {
  $locationProvider.html5Mode(true);
//  paginationTemplateProvider.setPath('directives/pagination.tpl.html')
});


angular.module('app').run(function($route,
                                   $rootScope,
                                   $timeout,
                                   $location) {

  /*
  this lets you change the args of the URL without reloading the whole view. from
     - https://github.com/angular/angular.js/issues/1699#issuecomment-59283973
     - http://joelsaupe.com/programming/angularjs-change-path-without-reloading/
     - https://github.com/angular/angular.js/issues/1699#issuecomment-60532290
  */
  var original = $location.path;
  $location.path = function (path, reload) {
      if (reload === false) {
          var lastRoute = $route.current;
          var un = $rootScope.$on('$locationChangeSuccess', function () {
              $route.current = lastRoute;
              un();
          });
        $timeout(un, 500)
      }
      return original.apply($location, [path]);
  };

});


angular.module('app').controller('AppCtrl', function($scope){

  // put this in a service later
  $scope.colorClass = function(percentile){
    return Math.ceil(percentile / 10)
  }

  /*
  $scope.$on('$routeChangeError', function(event, current, previous, rejection){
    RouteChangeErrorHandler.handle(event, current, previous, rejection)
  });

  $scope.$on('$routeChangeSuccess', function(next, current){
    security.requestCurrentUser().then(function(currentUser){
      Page.sendPageloadToSegmentio()
    })
  })

  $scope.$on('$locationChangeStart', function(event, next, current){
    ProductPage.loadingBar(next, current)
    Page.setProfileUrl(false)
    Loading.clear()
  })

  */

});


angular.module('articlePage', [
    'ngRoute'
  ])



  .config(function($routeProvider) {
    $routeProvider.when('/article/:pmid', {
      templateUrl: 'article-page/article-page.tpl.html',
      controller: 'articlePageCtrl'
    })
  })



  .controller("articlePageCtrl", function($scope,
                                          $http,
                                          $routeParams){

    console.log("article page!", $routeParams)
    $scope.refsetArticles = []

    var url = "api/article/" + $routeParams.pmid
    $http.get(url).success(function(resp){
      $scope.myArticle = resp
      _.each(resp.refset.articles, function(article){
        article.scopusInt = parseInt(article.scopus)
        $scope.refsetArticles.push(article)
      })
    })

  })  



angular.module('landingPage', [
    'ngRoute',
    'profileService'
  ])



  .config(function($routeProvider) {
    $routeProvider.when('/', {
      templateUrl: 'landing-page/landing.tpl.html',
      controller: 'landingPageCtrl'
    })
  })



  .controller("landingPageCtrl", function($scope, $http, ProfileService){
    console.log("loaded the landing page controller")
    $scope.newProfile = {}
    $scope.newProfile.coreJournals = [{}]

    $scope.makeProfile = function(){
      ProfileService.createProfile(
        $scope.newProfile.name,
        $scope.newProfile.pmids.split("\n"),
        _.pluck($scope.newProfile.coreJournals, "name")
      )
    }

    $scope.addCoreJournal = function(){
      console.log("adding a core journal field")
      $scope.newProfile.coreJournals.push({})
    }


    $scope.getJournalNames = function(nameStartsWith){
      return $http.get("api/journals/" + nameStartsWith)
      .then(function(resp){
          return resp.data
      })
    }

  })



angular.module('profilePage', [
    'ngRoute',
    'profileService'
  ])



  .config(function($routeProvider) {
    $routeProvider.when('/u/:slug', {
      templateUrl: 'profile-page/profile.tpl.html',
      controller: 'profilePageCtrl',
      resolve: {
        product: function(ProfileService, $route){
          return ProfileService.getProfile($route.current.params.slug)
        }
      }
    })
  })



  .controller("profilePageCtrl", function($scope,
                                          $routeParams,
                                          ProfileService){

    console.log("foo", ProfileService.data)

    console.log("$routeParams", $routeParams)

    $scope.ProfileService = ProfileService


  })



angular.module('articleService', [
  ])



  .factory("articleService", function($http,
                                      $timeout,
                                      $location){

    var data = {
      journals: {}
    }

    function getArticle(pmid){
      var url = "api/article/" + pmid
      console.log("getting profile for", slug)
      return $http.get(url).success(function(resp){
        data.profile = resp

        if (profileStillLoading()){
          $timeout(function(){
            getProfile(slug)
          }, 1000)
        }

      })
    }

    return {
      data: data,
      foo: function(){
        return "i am in the profile service"
      },

      createProfile: function(name, pmids, coreJournals) {
        console.log("i am making a profile:", name, pmids)
        var postData = {
          name: name,
          pmids: pmids,
          core_journals: coreJournals
        }
        $http.post("/profile",postData)
          .success(function(resp, status, headers){
            console.log("yay got a resp from /profile!", resp)
            $location.path("/u/" + resp.slug)
          })
      },

      getProfile: getProfile
    }


  })
angular.module('profileService', [
  ])



  .factory("ProfileService", function($http,
                                      $timeout,
                                      $location){

    var data = {
      profile: {
        articles:[]
      }
    }

    function profileStillLoading(){
      console.log("testing if profile still loading", data.profile.articles)
      return _.any(data.profile.articles, function(article){
        return _.isNull(article.percentile)
      })
    }

    function getProfile(slug){
      var url = "/profile/" + slug
      console.log("getting profile for", slug)
      return $http.get(url).success(function(resp){
        data.profile = resp

        if (profileStillLoading()){
          $timeout(function(){
            getProfile(slug)
          }, 1000)
        }

      })
    }

    return {
      data: data,
      foo: function(){
        return "i am in the profile service"
      },

      createProfile: function(name, pmids, coreJournals) {
        console.log("i am making a profile:", name, pmids)
        var postData = {
          name: name,
          pmids: pmids,
          core_journals: coreJournals
        }
        $http.post("/profile",postData)
          .success(function(resp, status, headers){
            console.log("yay got a resp from /profile!", resp)
            $location.path("/u/" + resp.slug)
          })
      },

      getProfile: getProfile
    }


  })
angular.module('templates.app', ['article-page/article-page.tpl.html', 'landing-page/landing.tpl.html', 'profile-page/profile.tpl.html']);

angular.module("article-page/article-page.tpl.html", []).run(["$templateCache", function($templateCache) {
  $templateCache.put("article-page/article-page.tpl.html",
    "<div class=\"article-page\">\n" +
    "   <div class=\"header\">\n" +
    "      <div class=\"articles-section\">\n" +
    "         <div class=\"article\" ng-show=\"myArticle\">\n" +
    "            <div class=\"metrics\">\n" +
    "               <a href=\"/article/{{ myArticle.pmid }}\"\n" +
    "                  tooltip-placement=\"left\"\n" +
    "                  tooltip=\"Citation percentile. Click to see comparison set.\"\n" +
    "                  class=\"percentile scale-{{ colorClass(myArticle.percentile) }}\">\n" +
    "                  <span class=\"val\" ng-show=\"article.percentile !== null\">\n" +
    "                     {{ myArticle.percentile }}\n" +
    "                  </span>\n" +
    "               </a>\n" +
    "               <span class=\"scopus scopus-small\"\n" +
    "                     tooltip-placement=\"left\"\n" +
    "                     tooltip=\"{{ article.citations }} citations via Scopus\">\n" +
    "                  {{ myArticle.citations }}\n" +
    "               </span>\n" +
    "               <span class=\"loading\" ng-show=\"article.percentile === null\">\n" +
    "                  <i class=\"fa fa-refresh fa-spin\"></i>\n" +
    "               </span>\n" +
    "            </div>\n" +
    "\n" +
    "            <div class=\"article-biblio\">\n" +
    "               <span class=\"title\">{{ myArticle.biblio.title }}</span>\n" +
    "               <span class=\"under-title\">\n" +
    "                  <span class=\"year\">({{ myArticle.biblio.year }})</span>\n" +
    "                  <span class=\"authors\">{{ myArticle.biblio.author_string }}</span>\n" +
    "                  <span class=\"journal\">{{ myArticle.biblio.journal }}</span>\n" +
    "                  <a class=\"linkout\"\n" +
    "                     href=\"http://www.ncbi.nlm.nih.gov/pubmed/{{ myArticle.biblio.pmid }}\">\n" +
    "                        <i class=\"fa fa-external-link\"></i>\n" +
    "                     </a>\n" +
    "               </span>\n" +
    "            </div>\n" +
    "         </div>\n" +
    "      </div>\n" +
    "   </div>\n" +
    "\n" +
    "   <div class=\"refset-articles-section articles-section\">\n" +
    "      <h3>Comparison set</h3>\n" +
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
    "   <form class=\"create-profile\"\n" +
    "         novalidate=\"novalidate\"\n" +
    "         ng-submit=\"makeProfile()\">\n" +
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
    "\n" +
    "\n" +
    "      <div class=\"core-journals\">\n" +
    "         <h3>What are the core journals in your field?</h3>\n" +
    "         <ul class=\"core-journals-list\">\n" +
    "            <li class=\"core-journal\"\n" +
    "                ng-form=\"coreJournalForm\"\n" +
    "                ng-repeat=\"coreJournal in newProfile.coreJournals\">\n" +
    "               <div class=\"form-group\">\n" +
    "                  <input name=\"core-journal-name\"\n" +
    "                         class=\"form-control input-lg\"\n" +
    "                         type=\"text\"\n" +
    "                         placeholder=\"Journal name\"\n" +
    "                         ng-model=\"coreJournal.name\"\n" +
    "                         typeahead=\"name for name in getJournalNames($viewValue)\"\n" +
    "                         typeahead-editable=\"false\"\n" +
    "                         required />\n" +
    "               </div>\n" +
    "            </li>\n" +
    "         </ul>\n" +
    "         <span class=\"btn btn-default btn-sm add-core-journal\" ng-click=\"addCoreJournal()\">\n" +
    "            <i class=\"fa fa-plus\"></i>\n" +
    "            Add a journal\n" +
    "         </span>\n" +
    "      </div>\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "\n" +
    "      <div class=\"submit-btn-container\">\n" +
    "         <button type=\"submit\" class=\"btn submit btn-lg btn-default\">\n" +
    "            Find my impact\n" +
    "         </button>\n" +
    "      </div>\n" +
    "\n" +
    "   </form>\n" +
    "\n" +
    "\n" +
    "\n" +
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
    "         <li ng-repeat=\"article in ProfileService.data.profile.articles | orderBy: '-percentile'\"\n" +
    "             class=\"article clearfix\">\n" +
    "\n" +
    "            <div class=\"metrics\">\n" +
    "               <a href=\"/article/{{ article.pmid }}\"\n" +
    "                  tooltip-placement=\"left\"\n" +
    "                  tooltip=\"Citation percentile. Click to see comparison set.\"\n" +
    "                  class=\"percentile scale-{{ colorClass(article.percentile) }}\">\n" +
    "                  <span class=\"val\" ng-show=\"article.percentile !== null\">\n" +
    "                     {{ article.percentile }}\n" +
    "                  </span>\n" +
    "               </a>\n" +
    "               <span class=\"scopus scopus-small\"\n" +
    "                     tooltip-placement=\"left\"\n" +
    "                     tooltip=\"{{ article.citations }} citations via Scopus\">\n" +
    "                  {{ article.citations }}\n" +
    "               </span>\n" +
    "               <span class=\"loading\" ng-show=\"article.percentile === null\">\n" +
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
