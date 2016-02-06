angular.module('personPage', [
    'ngRoute',
    'profileService',
    'directives.badge',
    "directives.languageIcon"
  ])



  .config(function($routeProvider) {
    $routeProvider.when('/person/:orcid', {
      templateUrl: 'person-page/person-page.tpl.html',
      controller: 'personPageCtrl',
      resolve: {
        personResp: function($http, $route){
          var url = "/api/profile/" + $route.current.params.orcid
          return $http.get(url)
        }
      }
    })
  })



  .controller("personPageCtrl", function($scope,
                                          $routeParams,
                                          ngProgress,
                                          FormatterService,
                                          personResp){
    ngProgress.complete()
    $scope.format = FormatterService
    $scope.person = personResp.data
    console.log("retrieved the person", $scope.person)






  })



