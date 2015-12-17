angular.module('personPage', [
    'ngRoute',
    'profileService',
    'directives.badge',
    "directives.languageIcon"
  ])



  .config(function($routeProvider) {
    $routeProvider.when('/person/:person_id', {
      templateUrl: 'person-page/person-page.tpl.html',
      controller: 'personPageCtrl',
      resolve: {
        personResp: function($http, $route){
          var url = "/api/person/" + $route.current.params.person_id
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



