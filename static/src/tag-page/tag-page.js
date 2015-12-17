angular.module('tagPage', [
    'ngRoute',
    'profileService',
    "directives.languageIcon"
  ])



  .config(function($routeProvider) {
    $routeProvider.when('/tag/:tagName', {
      templateUrl: 'tag-page/tag-page.tpl.html',
      controller: 'tagPageCtrl',
      resolve: {
        productsResp: function($http, $route){
          var url = "/api/leaderboard?type=packages&tag=" + $route.current.params.tagName
          return $http.get(url)
        }
      }
    })
  })



  .controller("tagPageCtrl", function($scope,
                                          $routeParams,
                                          ngProgress,
                                          FormatterService,
                                          productsResp){
    ngProgress.complete()
    $scope.format = FormatterService

    $scope.packages = productsResp.data
    console.log("retrieved the tag", productsResp)






  })



