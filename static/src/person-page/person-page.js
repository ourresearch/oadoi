angular.module('personPage', [
    'ngRoute',
    'person'
])



    .config(function($routeProvider) {
        $routeProvider.when('/u/:orcid', {
            templateUrl: 'person-page/person-page.tpl.html',
            controller: 'personPageCtrl',
            resolve: {
                personResp: function($http, $route, Person){
                    console.log("loaded the person response in the route def")
                    return Person.load($route.current.params.orcid)
                }
            }
        })
    })



    .controller("personPageCtrl", function($scope,
                                           $routeParams,
                                           Person,
                                           personResp){
        $scope.person = Person.d
        console.log("retrieved the person", $scope.person)








    })



