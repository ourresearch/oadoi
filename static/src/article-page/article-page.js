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


