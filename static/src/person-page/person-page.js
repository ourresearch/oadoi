angular.module('personPage', [
    'ngRoute'
    //,
    //'personService'
  ])



  .config(function($routeProvider) {
    $routeProvider.when('/u/:orcid', {
      templateUrl: 'person-page/person-page.tpl.html',
      controller: 'personPageCtrl',
      resolve: {
        personResp: function($http, $route){
            console.log("loaded the person response in the route def")
          var url = "/api/person/" + $route.current.params.orcid
          return $http.get(url)
        }
      }
    })
  })



  .controller("personPageCtrl", function($scope,
                                          $routeParams,
                                          personResp){
    $scope.person = personResp.data
    console.log("retrieved the person", $scope.person)






  })



